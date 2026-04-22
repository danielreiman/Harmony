# ============================================================================
#  AirVoice connector
# ----------------------------------------------------------------------------
#  Lets a Harmony agent join an AirVoice group call, listen to what people
#  say, decide what (if anything) to reply, speak a response out loud, and
#  optionally dispatch a computer-use task to the Harmony agent server.
#
#  Public functions (used by server/api.py):
#      enable(agent_id, host, username, password, model)  -> start a voice bot
#      disable(agent_id)                                  -> stop a voice bot
#      is_enabled(agent_id)                               -> check if running
#      enabled_ids()                                      -> set of running ids
# ============================================================================


# ----------------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------------

import asyncio           # needed to run the text-to-speech coroutine
import importlib         # lets us load optional voice libraries lazily
import json              # used to read / write structured messages
import os                # reads the AirVoice server address from the environment
import re                # finds wake words and normalises task text
import secrets           # generates a strong random password per session
import socket            # opens network connections to the voice server
import subprocess        # runs ffmpeg to decode the generated speech
import tempfile          # makes short-lived files for audio conversion
import threading         # runs the listener and the voice bot in parallel
import time              # measures delays and rate-limits repeated work
import wave              # saves microphone audio as a .wav file

import numpy             # stores audio samples as arrays of numbers
from ollama import Client  # talks to the Ollama AI service

import config            # holds the Ollama API key and other secrets


# ============================================================================
#                                 SETTINGS
# ----------------------------------------------------------------------------
#  All tunable values live here so nothing is hidden deeper in the file.
#  Names are written in plain English so non-technical readers can follow.
# ============================================================================


# ---- Where to connect --------------------------------------------------------

VOICE_SERVER_PORT = 1234        # port of the AirVoice call server
HARMONY_HOST      = "127.0.0.1" # address of our Harmony agent server
HARMONY_PORT      = 1223        # port of our Harmony agent server


# ---- AI model ----------------------------------------------------------------

DEFAULT_AI_MODEL = "ministral-3:3b-cloud"  # the thinking model to use by default

# Options passed to the model whenever we ask it to decide what to say.
# Low temperature keeps answers stable; small num_predict keeps them short.
THINKING_SETTINGS = {
    "temperature": 0,    # no randomness, same input gives same answer
    "num_predict": 80,   # cap the reply length
    "num_ctx":     1024, # how much text the model may look at
}


# ---- Audio format ------------------------------------------------------------

AUDIO_RATE          = 16000                        # samples per second
AUDIO_CHUNK_SIZE    = 320                          # samples per network packet
AUDIO_CHUNK_SECONDS = AUDIO_CHUNK_SIZE / AUDIO_RATE # length of one chunk in seconds
ID_BROADCAST_EVERY  = 5.0                          # resend our name this often
ECHO_IGNORE_TIME    = 0.8                          # ignore mic right after we speak


# ---- Listening ---------------------------------------------------------------

QUIET_THRESHOLD     = 400   # volume below this counts as silence
SILENCE_TO_FINISH   = 1.0   # seconds of silence that end a sentence
MIN_SPEECH_SECONDS  = 0.3   # anything shorter than this is ignored


# ---- Brain -------------------------------------------------------------------

WAKE_WORDS            = re.compile(r"\b(?:harmony|agent)\b", re.IGNORECASE)  # words that address us
CONVERSATION_MEMORY   = 4        # how many recent lines we remember
REPEAT_TASK_COOLDOWN  = 20       # don't resend the same task faster than this
SPEAKING_VOICE        = "en-US-GuyNeural"  # Edge-TTS voice name
SPEAKING_SPEED        = "+0%"    # how fast we talk, in percent from normal


# ---- Decision prompt ---------------------------------------------------------
#  This is the system prompt sent to the AI model. It explains the rules of
#  the conversation and asks for a JSON reply so we can parse it safely.

DECISION_PROMPT = (
    'You are a voice participant in a group call, joining as "{name}".\n'
    'You hear meeting audio and may answer with spoken words.\n'
    '\n'
    'You may dispatch a task to a Harmony computer-use agent only when someone asks\n'
    'for real computer work.\n'
    '\n'
    'Return one JSON object only:\n'
    '  {{"say": "<what to speak, or empty string>", "task": "<computer task, or empty string>"}}\n'
    '\n'
    'Rules:\n'
    '- The wake words are "Harmony" and "Agent".\n'
    '- If the current line contains a wake word and asks to open, search, click,\n'
    '  type, write, run, install, create, organize, close, or control the computer,\n'
    '  fill "task".\n'
    '- If you say you are doing a computer action, "task" must not be empty.\n'
    '- Reply only when addressed by a wake word or when the request is clearly for the AI.\n'
    '- Keep "say" under 18 words.\n'
    '- If dispatching a task, say a short acknowledgement that fits the task.\n'
    '- Do not say "I\'ll do that" or "I will do that".\n'
    '- If no reply is needed, return {{"say": "", "task": ""}}.'
)


# ============================================================================
#                              SMALL HELPERS
# ============================================================================


def is_addressed(text):
    # True when the sentence contains one of our wake words ("Harmony" / "Agent").
    return WAKE_WORDS.search(text) is not None


def fingerprint(text):
    # Normalise a task string to a stable key so we can spot repeats.
    # Lowercases the text and keeps only letters and digits.
    words = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(words)


def save_wav(audio, path):
    # Write a mono 16-bit PCM .wav file so speech-recognition can read it.
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)                                 # mono audio
        wav.setsampwidth(2)                                 # 16 bits per sample
        wav.setframerate(AUDIO_RATE)                        # samples per second
        wav.writeframes(audio.astype(numpy.int16).tobytes())  # raw sample bytes


# ============================================================================
#                           TASK DISPATCH (to Harmony)
# ----------------------------------------------------------------------------
#  Opens a short TCP connection to the Harmony agent server and asks it to
#  run a natural-language computer task on behalf of this voice bot.
# ============================================================================


class TaskSender:

    def __init__(self, host=HARMONY_HOST, port=HARMONY_PORT, agent_id=None):
        self.host     = host       # where the Harmony agent server lives
        self.port     = port       # which port it listens on
        self.agent_id = agent_id   # id of the agent that should run the task

    def send(self, task):
        # Build the request the Harmony server expects.
        payload = {"action": "send_task", "task": task}

        # Attach the agent id when we know it (the server uses this to route).
        if self.agent_id:
            payload["agent_id"] = self.agent_id

        # Serialize to bytes because the protocol is length-prefixed binary.
        body = json.dumps(payload).encode()

        try:
            # A single short-lived connection per task keeps things simple.
            with socket.create_connection((self.host, self.port), timeout=5) as sock:

                # Protocol: 8-byte big-endian length, then the JSON body.
                sock.sendall(len(body).to_bytes(8, "big") + body)

                # Read the 8-byte length of the reply.
                header = sock.recv(8)
                if len(header) < 8:
                    return False

                # Decode the length and read that many bytes of reply.
                length = int.from_bytes(header, "big")
                data = b""
                while len(data) < length:
                    chunk = sock.recv(length - len(data))
                    if not chunk:
                        break
                    data += chunk

            # The server replies with JSON including a "success" flag.
            reply = json.loads(data.decode())
            return bool(reply.get("success"))

        except (OSError, ValueError):
            # Network error or malformed reply - treat as "task failed".
            return False


# ============================================================================
#                         VOICE  (speech <-> text)
# ----------------------------------------------------------------------------
#  Uses Google's free speech recogniser for speech-to-text, and Microsoft's
#  Edge-TTS for text-to-speech. ffmpeg (via imageio-ffmpeg) converts the
#  mp3 Edge-TTS returns into raw PCM we can send over the call.
# ============================================================================


class Voice:

    def __init__(self, voice_name=SPEAKING_VOICE, speak_rate=SPEAKING_SPEED, lang="en-US"):

        # speech_recognition and edge_tts are optional deps; import lazily
        # so the module still loads if the user has not installed them yet.
        sr_module       = importlib.import_module("speech_recognition")
        edge_tts_module = importlib.import_module("edge_tts")
        ffmpeg_module   = importlib.import_module("imageio_ffmpeg")

        self.sr       = sr_module           # speech-to-text library
        self.edge_tts = edge_tts_module     # text-to-speech library
        self.ffmpeg   = ffmpeg_module.get_ffmpeg_exe()  # path to ffmpeg binary

        # Build the Google recogniser and fix its energy threshold.
        # A fixed threshold stops it from "auto-adapting" to a silent room.
        self.recogniser = sr_module.Recognizer()
        self.recogniser.dynamic_energy_threshold = False
        self.recogniser.energy_threshold = 250

        # Remember the user-chosen voice / rate / language.
        self.voice_name = voice_name
        self.speak_rate = speak_rate
        self.lang       = lang

        print("[Airvoice] Voice ready (Google STT + Edge TTS)")

    # -- Speech to text --------------------------------------------------------

    def to_text(self, audio):
        # Nothing to transcribe if we received no samples.
        if audio.size == 0:
            return ""

        # Write the samples to a temp .wav so the recogniser can open it.
        with tempfile.TemporaryDirectory(prefix="airvoice-stt-") as folder:
            wav_path = os.path.join(folder, "heard.wav")
            save_wav(audio, wav_path)

            try:
                # Load the wav and ask Google to transcribe it.
                with self.sr.AudioFile(wav_path) as source:
                    recorded = self.recogniser.record(source)
                return self.recogniser.recognize_google(recorded, language=self.lang).strip()

            except self.sr.UnknownValueError:
                # Google heard nothing it could turn into words.
                return ""
            except Exception as error:
                # Any other failure (network, quota, etc.) we log and skip.
                print(f"[Airvoice] STT error: {error}")
                return ""

    # -- Text to speech --------------------------------------------------------

    def to_audio(self, text):
        # Nothing to say -> return an empty sample array.
        if not text:
            return numpy.zeros(0, dtype=numpy.int16)

        with tempfile.TemporaryDirectory(prefix="airvoice-tts-") as folder:
            try:
                mp3_path = os.path.join(folder, "reply.mp3")

                # Edge-TTS is async-only so we run it inside asyncio.run.
                asyncio.run(self._write_mp3(text, mp3_path))

                # Convert the mp3 to raw PCM samples matching our call rate.
                return self._mp3_to_samples(mp3_path)

            except Exception as error:
                print(f"[Airvoice] TTS error: {error}")
                return numpy.zeros(0, dtype=numpy.int16)

    async def _write_mp3(self, text, path):
        # Call Edge-TTS and save the resulting audio to the given path.
        speaker = self.edge_tts.Communicate(text, self.voice_name, rate=self.speak_rate)
        await speaker.save(path)

    def _mp3_to_samples(self, path):
        # Decode the mp3 with ffmpeg to signed 16-bit little-endian mono PCM
        # at our call sample rate. stdout contains the raw bytes.
        result = subprocess.run(
            [
                self.ffmpeg,
                "-hide_banner", "-loglevel", "error",
                "-i", path,
                "-f", "s16le",              # raw 16-bit samples
                "-ac", "1",                 # mono
                "-ar", str(AUDIO_RATE),     # match call rate
                "-",                        # write to stdout
            ],
            check=True,
            capture_output=True,
        )
        return numpy.frombuffer(result.stdout, dtype=numpy.int16).copy()


def make_voice():
    # Build a Voice with the defaults defined at the top of this file.
    return Voice(
        voice_name = SPEAKING_VOICE,
        speak_rate = SPEAKING_SPEED,
        lang       = "en-US",
    )


# ============================================================================
#                      CALL  (network link to the voice server)
# ----------------------------------------------------------------------------
#  Two sockets: a TCP command channel for text messages (REGISTER / LOGIN /
#  INCOMING / ...) and a UDP channel for raw audio packets.
# ============================================================================


class Call:

    def __init__(self, server_host, username, password, on_message, on_audio):
        self.server_host  = server_host   # where the AirVoice server lives
        self.username     = username      # our display / login name
        self.password     = password      # our password
        self.on_message   = on_message    # callback for text lines
        self.on_audio     = on_audio      # callback for audio chunks
        self.cmd_socket   = None          # TCP socket for commands
        self.voice_socket = None          # UDP socket for audio
        self.voice_port   = None          # server's UDP port for audio
        self.is_connected = False         # True once TCP is up

    # -- Connection management -------------------------------------------------

    def connect(self):
        # Build the TCP command socket and connect to the server.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)                                      # fail fast if unreachable
        sock.connect((self.server_host, VOICE_SERVER_PORT))
        sock.settimeout(None)                                   # now block forever on recv

        self.cmd_socket   = sock
        self.is_connected = True

        # Read server messages in a background thread so callers are not blocked.
        threading.Thread(target=self._listen_for_messages, daemon=True).start()

    def close(self):
        # Mark disconnected first so the background threads stop looping.
        self.is_connected = False
        self._drop_voice_socket()

        # Close the TCP command socket if we still have it.
        if self.cmd_socket:
            try:
                self.cmd_socket.close()
            except OSError:
                pass
            self.cmd_socket = None

    # -- Sending ---------------------------------------------------------------

    def send(self, text):
        # Send one line of text over the command socket. Lines are \n-terminated.
        if not self.cmd_socket:
            return
        try:
            self.cmd_socket.sendall((text + "\n").encode())
        except OSError:
            self.is_connected = False

    def send_audio(self, audio):
        # Send one chunk of audio over UDP. No retry, UDP is fire-and-forget.
        if not (self.voice_socket and self.voice_port):
            return
        try:
            self.voice_socket.sendto(audio.tobytes(), (self.server_host, self.voice_port))
        except OSError:
            pass

    # -- Voice (UDP) channel ---------------------------------------------------

    def open_voice(self, port):
        # Drop any existing UDP socket so we always start clean.
        self._drop_voice_socket()

        # Bind to any free local port; the server learns our port from the first packet.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", 0))
        sock.settimeout(0.5)

        self.voice_socket = sock
        self.voice_port   = port

        # Announce our name so the server knows who this UDP flow belongs to.
        self._announce_identity()

        # Start reading audio in the background.
        threading.Thread(target=self._listen_for_audio, args=(sock,), daemon=True).start()

    def _drop_voice_socket(self):
        sock = self.voice_socket   # grab current socket (may be None)
        self.voice_socket = None   # clear first so other threads stop using it
        self.voice_port   = None
        if sock:
            try:
                sock.close()
            except OSError:
                pass

    def _announce_identity(self):
        # Tell the server "my UDP flow is user X" by sending a few ID packets.
        if not (self.voice_socket and self.voice_port):
            return
        packet = f"ID:{self.username}".encode()
        for _ in range(3):
            try:
                self.voice_socket.sendto(packet, (self.server_host, self.voice_port))
            except OSError:
                return
            time.sleep(0.01)   # a small pause between duplicates

    # -- Background listeners --------------------------------------------------

    def _listen_for_messages(self):
        # Read text lines from the TCP command socket and forward to callback.
        buffer = ""
        sock   = self.cmd_socket

        try:
            while self.is_connected:
                data = sock.recv(4096)

                # Empty read means the server closed the connection.
                if not data:
                    break

                buffer += data.decode(errors="replace")

                # Process every complete \n-terminated line in the buffer.
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.on_message(line)

        except OSError:
            pass
        finally:
            self.is_connected = False

    def _listen_for_audio(self, sock):
        # Read UDP audio packets. Re-announce our name periodically so the
        # server keeps associating this flow with the right user.
        last_ping = time.monotonic()

        while self.voice_socket is sock:
            try:
                raw = sock.recvfrom(65535)[0]
            except socket.timeout:
                # No packets recently - keep the server aware we're still here.
                if time.monotonic() - last_ping > ID_BROADCAST_EVERY:
                    self._announce_identity()
                    last_ping = time.monotonic()
                continue
            except OSError:
                break

            # Ignore obviously malformed packets (odd byte count etc.).
            if len(raw) < 2 or len(raw) % 2 != 0:
                continue

            # Convert the packet bytes into a numpy int16 sample array.
            samples = numpy.frombuffer(raw, dtype=numpy.int16).copy()
            self.on_audio(samples)


# ============================================================================
#                        EAR  (sentence-finishing buffer)
# ----------------------------------------------------------------------------
#  Collects incoming audio chunks until the speaker pauses long enough for
#  us to treat what was said as one complete sentence.
# ============================================================================


class Ear:

    def __init__(self):
        self.chunks       = []   # audio pieces received so far
        self.speech_count = 0    # total samples that sounded like speech
        self.quiet_count  = 0    # trailing samples that sounded like silence

    def add(self, audio):
        # Root-mean-square of the samples gives a rough volume measurement.
        if audio.size:
            rms = float(numpy.sqrt(numpy.mean(audio.astype(numpy.float32) ** 2)))
        else:
            rms = 0.0

        # Always keep the chunk so we can replay the whole sentence later.
        self.chunks.append(audio)

        if rms >= QUIET_THRESHOLD:
            # Loud enough to count as speech - reset the trailing-silence counter.
            self.speech_count += audio.size
            self.quiet_count   = 0
        else:
            # Silence - extend the trailing-silence counter.
            self.quiet_count += audio.size

    def ready(self):
        # A sentence is ready once we have enough speech followed by enough silence.
        enough_speech  = self.speech_count >= MIN_SPEECH_SECONDS * AUDIO_RATE
        enough_silence = self.quiet_count  >= SILENCE_TO_FINISH  * AUDIO_RATE
        return enough_speech and enough_silence

    def take(self):
        # Return the full sentence as one array and reset the buffer.
        if self.chunks:
            audio = numpy.concatenate(self.chunks)
        else:
            audio = numpy.zeros(0, dtype=numpy.int16)

        self.chunks       = []
        self.speech_count = 0
        self.quiet_count  = 0
        return audio


# ============================================================================
#                      BRAIN  (the voice bot for one agent)
# ----------------------------------------------------------------------------
#  Ties everything together: joins a call, listens, asks the AI what to do,
#  optionally dispatches a Harmony task, and speaks the reply.
# ============================================================================


class Brain:

    def __init__(self, server_host, username, password, model, agent_id=None):
        self.server_host = server_host          # AirVoice server address
        self.username    = username             # our login name
        self.password    = password             # our password
        self.model       = model                # AI model name
        self.agent_id    = agent_id             # which Harmony agent runs tasks
        self.prompt      = DECISION_PROMPT.format(name=username)

        # Conversation state.
        self.meeting_log = []    # recent sentences for context
        self.in_call     = False # True once we are inside an active call
        self.speaking    = False # True while we are playing our own voice
        self.quiet_until = 0.0   # ignore mic until monotonic time reaches this
        self.last_key    = ""    # fingerprint of last task we dispatched
        self.last_sent   = 0.0   # when we dispatched the last task

        # Concurrency guards so the mic and the AI do not race each other.
        self.ear        = Ear()
        self.ear_lock   = threading.Lock()
        self.mouth_lock = threading.Lock()

        # Ollama requires an API key which we load from the shared config.
        api_key = config.OLLAMA_API_KEY
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY not found")

        # Build the AI client, the voice system, the task sender, the call link.
        self.ai    = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self.voice = make_voice()
        self.tasks = TaskSender(agent_id=agent_id)
        self.call  = Call(
            server_host, username, password,
            on_message = lambda line:  self.hear(text_line=line),
            on_audio   = lambda audio: self.hear(audio=audio),
        )

    # -- Lifecycle -------------------------------------------------------------

    def activate(self):
        # Connect to the server, register, log in, then idle while the
        # background threads handle messages and audio.
        try:
            self.call.connect()
        except OSError as error:
            print(f"[Airvoice] Cannot connect: {error}")
            return

        self.call.send(f"REGISTER {self.username} {self.password}")
        self.call.send(f"LOGIN {self.username} {self.password}")

        try:
            while self.call.is_connected:
                time.sleep(0.2)  # don't busy-loop
                self.hear()      # check if a sentence is ready
        finally:
            self.call.close()

    def stop(self):
        # Politely leave the call, then tear down the sockets.
        self.call.send("QUIT")
        self.call.close()

    # -- Input handling --------------------------------------------------------

    def hear(self, text_line=None, audio=None):
        # Case A: a text message arrived from the server.
        if text_line is not None:
            self._handle_server_message(text_line)
            return

        # Case B: an audio chunk arrived from the server.
        if audio is not None:
            self._handle_audio_chunk(audio)
            return

        # Case C: periodic tick - check whether a full sentence is ready.
        with self.ear_lock:
            if not self.ear.ready():
                return
            audio = self.ear.take()

        # Turn the captured sentence into text.
        heard = self.voice.to_text(audio).strip()
        if not heard:
            return

        # Only react when a wake word is spoken.
        if is_addressed(heard):
            self.think(heard)

    def _handle_server_message(self, line):
        # Split the server line into a command and arguments.
        parts   = line.split()
        command = parts[0].upper() if parts else ""
        args    = parts[1:]

        if command == "INCOMING" and args:
            # Someone is calling us - accept immediately.
            self.call.send(f"ACCEPT {args[0]}")

        elif command == "CALL_START" and args:
            # Server tells us which UDP port to use for audio.
            try:
                self.call.open_voice(int(args[0]))
            except ValueError:
                pass

        elif command == "PARTICIPANTS":
            # We are now officially in the call.
            self.in_call = True

        elif command in ("CALL_ENDED", "HANGUP_OK"):
            # Call is over - reset everything.
            self.in_call = False
            with self.ear_lock:
                self.ear = Ear()

    def _handle_audio_chunk(self, audio):
        # Only listen when we're in a call, not speaking, and past the echo window.
        if not self.in_call:
            return
        if self.speaking:
            return
        if time.monotonic() < self.quiet_until:
            return

        with self.ear_lock:
            self.ear.add(audio)

    # -- Thinking / acting -----------------------------------------------------

    def think(self, heard):
        # Remember this line, capped at the last CONVERSATION_MEMORY entries.
        self.meeting_log = (self.meeting_log + [heard])[-CONVERSATION_MEMORY:]

        # Build a short transcript for context.
        context = "\n".join(f"- {line}" for line in self.meeting_log)

        # Ask the AI what to say and what (if any) task to dispatch.
        reply = self._ask_ai(
            [
                {"role": "system", "content": self.prompt},
                {"role": "user",   "content": f"Recent lines:\n{context}\n\nNow: {heard}\nDecide."},
            ],
            THINKING_SETTINGS,
            "AI error",
        )
        if not reply:
            return

        # Pull the two expected fields out of the JSON reply.
        to_say  = str(reply.get("say",  "")).strip()
        to_do   = str(reply.get("task", "")).strip()

        # Dispatch the task, but suppress duplicates fired in quick succession.
        if to_do:
            is_repeat   = fingerprint(to_do) == self.last_key
            fresh_fire  = time.monotonic() - self.last_sent < REPEAT_TASK_COOLDOWN
            if is_repeat and fresh_fire:
                return

            if self.tasks.send(to_do):
                self.last_key  = fingerprint(to_do)
                self.last_sent = time.monotonic()

        # Speak the spoken reply (if any).
        if to_say:
            self.talk(to_say)

    def talk(self, text):
        # Speak some text back into the call.
        if not text:
            return

        with self.mouth_lock:
            # Flip the "we are speaking" flag so we ignore our own echo.
            self.speaking = True

            # Clear the listener so we don't pick up our own voice.
            with self.ear_lock:
                self.ear = Ear()

            try:
                # Generate the raw audio samples for the text.
                audio = self.voice.to_audio(text)
                if not audio.size:
                    return

                # Send the samples as a stream of fixed-size chunks, paced in
                # real time so the server and listeners don't get flooded.
                start = time.monotonic()
                for index, offset in enumerate(range(0, audio.size, AUDIO_CHUNK_SIZE)):

                    # Copy this slice into a fixed-size zero-padded chunk.
                    slice_      = audio[offset:offset + AUDIO_CHUNK_SIZE]
                    chunk       = numpy.zeros(AUDIO_CHUNK_SIZE, dtype=numpy.int16)
                    chunk[:slice_.size] = slice_

                    # Sleep so packets leave at roughly real-time speed.
                    next_send = start + index * AUDIO_CHUNK_SECONDS
                    wait      = next_send - time.monotonic()
                    if wait > 0:
                        time.sleep(wait)

                    self.call.send_audio(chunk)

            finally:
                # Ignore mic for a short time so our own tail-end doesn't
                # loop back into the listener.
                self.quiet_until = time.monotonic() + ECHO_IGNORE_TIME
                with self.ear_lock:
                    self.ear = Ear()
                self.speaking = False

    def _ask_ai(self, messages, options, label):
        # Query Ollama and parse the JSON content it returns.
        try:
            response = self.ai.chat(
                model    = self.model,
                messages = messages,
                format   = "json",
                options  = options,
            )
            raw = (response.get("message", {}).get("content") or "").strip()
            if not raw:
                return {}
            return json.loads(raw)

        except Exception as error:
            print(f"[Airvoice] {label}: {error}")
            return {}


# ============================================================================
#                           PUBLIC  enable / disable
# ----------------------------------------------------------------------------
#  Keep a dict of running brains keyed by agent id. enable() starts one on
#  a background thread; disable() tears it down.
# ============================================================================


_running       = {}                  # agent_id -> Brain that's currently active
_running_lock  = threading.Lock()    # protects _running from concurrent edits


def _run_brain(agent_id, brain):
    # Internal: run a brain on its own thread and unregister it when done.
    try:
        brain.activate()
    finally:
        with _running_lock:
            _running.pop(agent_id, None)


def enable(agent_id):
    # Turn the voice bot on for the given agent. No-op if already running.
    with _running_lock:
        if agent_id in _running:
            return True

    # The server IP is the only setting still pulled from the environment.
    # Everything else is decided here in code.
    server_host = os.environ.get("AIRVOICE_HOST", "127.0.0.1")

    # The AirVoice login name prefixes the agent id so it's clear it's a bot.
    user_name = f"Agent {agent_id}"

    # Generate a fresh random password for this session. It never leaves
    # memory: no env var, no file, no database. Each call to enable() gets
    # a brand-new password that is used once and then forgotten.
    user_pass = secrets.token_urlsafe(24)

    # The AI model is the default defined at the top of this file.
    model_name = DEFAULT_AI_MODEL

    # Build the brain outside the lock (network / AI setup can be slow).
    brain = Brain(server_host, user_name, user_pass, model_name, agent_id=agent_id)

    # Re-check under the lock in case another thread got there first.
    with _running_lock:
        if agent_id in _running:
            return True
        _running[agent_id] = brain

    # Run the brain on a daemon thread so it dies with the process.
    threading.Thread(target=_run_brain, args=(agent_id, brain), daemon=True).start()

    print(f"[Airvoice] Enabled for {agent_id} ({user_name}@{server_host})")
    return True


def disable(agent_id):
    # Turn the voice bot off for the given agent.
    with _running_lock:
        brain = _running.pop(agent_id, None)

    if not brain:
        return False

    try:
        brain.stop()
    except Exception:
        # Best-effort cleanup - ignore errors while shutting down.
        pass

    print(f"[Airvoice] Disabled for {agent_id}")
    return True


def is_enabled(agent_id):
    # True if a voice bot is currently running for this agent.
    with _running_lock:
        return agent_id in _running


def enabled_ids():
    # Snapshot of every agent id that currently has a voice bot running.
    with _running_lock:
        return set(_running.keys())
