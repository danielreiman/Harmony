"""AirVoice connector for Harmony.

Whole workflow:
1. Log in to the AirVoice server as the Harmony agent.
2. Accept an incoming call.
3. Receive voice audio from the call.
4. Turn the voice audio into text.
5. If the text says "Harmony" or "Agent", decide what to do.
6. Send computer tasks to Harmony when needed.
7. Turn the reply text into voice audio.
8. Send the voice audio back to the AirVoice call.
"""

import asyncio
import importlib
import json
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import wave

import numpy
from ollama import Client

import config
import database as db
from helpers import extract_json as read_json_object_from_text


# Network settings.
AIRVOICE_SERVER_PORT = 1234
HARMONY_API_HOST = "127.0.0.1"
HARMONY_API_PORT = 1223


# Model settings.
DEFAULT_MODEL_NAME = "ministral-3:3b-cloud"
MODEL_OPTIONS = {
    "temperature": 0,
    "num_predict": 80,
    "num_ctx": 1024,
}
SHORT_SPOKEN_LINE_OPTIONS = {
    "temperature": 0.4,
    "num_predict": 45,
    "num_ctx": 512,
}
RECAP_SPOKEN_LINE_OPTIONS = {
    "temperature": 0,
    "num_predict": 55,
    "num_ctx": 768,
}


# Call audio settings.
CALL_AUDIO_SAMPLE_RATE = 16000
BYTES_PER_AUDIO_SAMPLE = 2
AUDIO_SAMPLES_PER_PACKET = 320
AUDIO_PACKET_SECONDS = AUDIO_SAMPLES_PER_PACKET / CALL_AUDIO_SAMPLE_RATE
SEND_NAME_TO_VOICE_SERVER_EVERY_SECONDS = 5.0
IGNORE_CALL_AUDIO_AFTER_SPEAKING_SECONDS = 0.8


# Speech detection settings.
SILENCE_VOLUME_LEVEL = 400
SILENCE_SECONDS_THAT_FINISH_SPEECH = 1.0
MINIMUM_SPEECH_SECONDS = 0.3


# Voice command settings.
WAKE_WORDS = ("harmony", "agent")
WAKE_WORD_PATTERN = re.compile(r"\b(?:harmony|agent)\b", re.IGNORECASE)
RECENT_LINES_TO_REMEMBER = 4
DUPLICATE_TASK_IGNORE_SECONDS = 20
TEXT_TO_SPEECH_VOICE = "en-US-GuyNeural"
TEXT_TO_SPEECH_RATE = "+0%"
TASK_RESULT_CHECK_SECONDS = 1.0
TASK_RESULT_MAX_WAIT_SECONDS = 300
TASK_START_WORDS = (
    "open",
    "launch",
    "start",
    "search",
    "google",
    "find",
    "go to",
    "visit",
    "click",
    "type",
    "write",
    "create",
    "make",
    "run",
    "close",
    "install",
    "send",
    "scroll",
    "organize",
    "arrange",
    "clean",
    "turn",
)

HEARD_TASK_START_FIXES = {
    "opened": "open",
    "opening": "open",
    "searched": "search",
    "searching": "search",
    "closed": "close",
    "closing": "close",
    "organized": "organize",
    "organised": "organize",
    "organizing": "organize",
    "arranged": "arrange",
    "arranging": "arrange",
    "cleaned": "clean",
    "cleaning": "clean",
}

TASK_REPLY_WORDS = (
    "opening",
    "searching",
    "checking",
    "closing",
    "creating",
    "organizing",
    "arranging",
    "cleaning",
    "starting",
    "running",
    "installing",
    "sending",
    "typing",
    "writing",
    "clicking",
    "scrolling",
)
VOICE_DECISION_PROMPT = """You are a voice participant in a group call, joining as "{name}".
You hear meeting audio and may answer with spoken words.

You may dispatch a task to a Harmony computer-use agent only when someone asks
for real computer work.

Return one JSON object only:
  {{"say": "<what to speak, or empty string>", "task": "<computer task, or empty string>"}}

Rules:
- The wake words are "Harmony" and "Agent".
- If the current line contains a wake word and asks to open, search, click,
  type, write, run, install, create, organize, close, or control the computer,
  fill "task".
- If you say you are doing a computer action, "task" must not be empty.
- Reply only when addressed by a wake word or when the request is clearly for the AI.
- Keep "say" under 18 words.
- If dispatching a task, say a short acknowledgement that fits the task.
- Do not say "I'll do that" or "I will do that".
- If no reply is needed, return {{"say": "", "task": ""}}."""


def write_call_audio_to_wave_file(audio_samples, wave_file_path):
    with wave.open(wave_file_path, "wb") as wave_file:
        wave_file.setnchannels(1)
        wave_file.setsampwidth(BYTES_PER_AUDIO_SAMPLE)
        wave_file.setframerate(CALL_AUDIO_SAMPLE_RATE)
        wave_file.writeframes(audio_samples.astype(numpy.int16).tobytes())


class LocalSpeechTools:
    """Turns call audio into text and turns reply text into call audio."""

    def __init__(
        self,
        text_to_speech_voice=TEXT_TO_SPEECH_VOICE,
        text_to_speech_rate=TEXT_TO_SPEECH_RATE,
        speech_to_text_language="en-US",
    ):
        speech_recognition = importlib.import_module("speech_recognition")
        edge_text_to_speech = importlib.import_module("edge_tts")
        ffmpeg_tools = importlib.import_module("imageio_ffmpeg")

        self.speech_recognition = speech_recognition
        self.speech_recognizer = speech_recognition.Recognizer()
        self.speech_recognizer.dynamic_energy_threshold = False
        self.speech_recognizer.energy_threshold = 250

        self.edge_text_to_speech = edge_text_to_speech
        self.ffmpeg_path = ffmpeg_tools.get_ffmpeg_exe()
        self.text_to_speech_voice = text_to_speech_voice
        self.text_to_speech_rate = text_to_speech_rate
        self.speech_to_text_language = speech_to_text_language

        print("[Airvoice] Speech: SpeechRecognition Google, Edge TTS")

    def turn_heard_audio_into_text(self, audio_samples):
        if audio_samples.size == 0:
            return ""

        with tempfile.TemporaryDirectory(prefix="airvoice-stt-") as temporary_folder_path:
            heard_wave_file_path = os.path.join(temporary_folder_path, "heard.wav")
            write_call_audio_to_wave_file(audio_samples, heard_wave_file_path)

            try:
                with self.speech_recognition.AudioFile(heard_wave_file_path) as audio_file:
                    recorded_audio = self.speech_recognizer.record(audio_file)
                return self.recognize_recorded_audio(recorded_audio)
            except self.speech_recognition.UnknownValueError:
                return ""
            except self.speech_recognition.RequestError as error:
                print(f"[Airvoice] STT error: {error}")
                return ""
            except Exception as error:
                print(f"[Airvoice] STT error: {error}")
                return ""

    def recognize_recorded_audio(self, recorded_audio):
        return self.speech_recognizer.recognize_google(
            recorded_audio,
            language=self.speech_to_text_language,
        ).strip()

    def turn_text_into_call_audio(self, text_to_say):
        if not text_to_say:
            return numpy.zeros(0, dtype=numpy.int16)

        with tempfile.TemporaryDirectory(prefix="airvoice-tts-") as temporary_folder_path:
            try:
                speech_file_path = os.path.join(temporary_folder_path, "reply.mp3")
                asyncio.run(self.create_audio_with_edge_tts(text_to_say, speech_file_path))
                return self.read_generated_audio_file_as_call_audio(speech_file_path)
            except Exception as error:
                print(f"[Airvoice] TTS error: {error}")
                return numpy.zeros(0, dtype=numpy.int16)

    async def create_audio_with_edge_tts(self, text_to_say, output_audio_file_path):
        voice = self.text_to_speech_voice or TEXT_TO_SPEECH_VOICE
        communicator = self.edge_text_to_speech.Communicate(
            text_to_say,
            voice,
            rate=self.text_to_speech_rate,
        )
        await communicator.save(output_audio_file_path)

    def read_generated_audio_file_as_call_audio(self, audio_file_path):
        result = subprocess.run(
            [
                self.ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                audio_file_path,
                "-f",
                "s16le",
                "-ac",
                "1",
                "-ar",
                str(CALL_AUDIO_SAMPLE_RATE),
                "-",
            ],
            check=True,
            capture_output=True,
        )
        return numpy.frombuffer(result.stdout, dtype=numpy.int16).copy()



class AirvoiceServerConnection:
    """Handles AirVoice TCP commands and UDP voice packets."""

    def __init__(
        self,
        server_host,
        username,
        password,
        when_text_line_arrives,
        when_audio_samples_arrive,
    ):
        self.server_host = server_host
        self.username = username
        self.password = password
        self.when_text_line_arrives = when_text_line_arrives
        self.when_audio_samples_arrive = when_audio_samples_arrive

        self.text_socket = None
        self.voice_socket = None
        self.voice_port = None
        self.is_connected = False

    def connect_to_server(self):
        text_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        text_socket.settimeout(5)
        text_socket.connect((self.server_host, AIRVOICE_SERVER_PORT))
        text_socket.settimeout(None)

        self.text_socket = text_socket
        self.is_connected = True

        threading.Thread(
            target=self.read_text_lines_from_server_forever,
            daemon=True,
        ).start()

    def send_text_line(self, text_line):
        if not self.text_socket:
            return

        try:
            self.text_socket.sendall((text_line + "\n").encode())
        except OSError:
            self.is_connected = False

    def open_voice_stream(self, voice_port):
        self.close_voice_stream()

        voice_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        voice_socket.bind(("", 0))
        voice_socket.settimeout(0.5)

        self.voice_socket = voice_socket
        self.voice_port = voice_port

        self.send_name_to_voice_server()
        threading.Thread(
            target=self.read_audio_packets_from_server_forever,
            args=(voice_socket,),
            daemon=True,
        ).start()

    def send_audio_to_call(self, audio_samples):
        if not (self.voice_socket and self.voice_port):
            return

        try:
            self.voice_socket.sendto(
                audio_samples.tobytes(),
                (self.server_host, self.voice_port),
            )
        except OSError:
            pass

    def close_connection(self):
        self.is_connected = False
        self.close_voice_stream()

        if self.text_socket:
            try:
                self.text_socket.close()
            except OSError:
                pass
            self.text_socket = None

    def send_name_to_voice_server(self):
        if not (self.voice_socket and self.voice_port):
            return

        name_packet = f"ID:{self.username}".encode()
        for repeat_number in range(3):
            try:
                self.voice_socket.sendto(name_packet, (self.server_host, self.voice_port))
            except OSError:
                return
            time.sleep(0.01)

    def close_voice_stream(self):
        voice_socket = self.voice_socket
        self.voice_socket = None
        self.voice_port = None

        if voice_socket:
            try:
                voice_socket.close()
            except OSError:
                pass

    def read_text_lines_from_server_forever(self):
        received_text = ""
        text_socket = self.text_socket

        try:
            while self.is_connected:
                received_bytes = text_socket.recv(4096)
                if not received_bytes:
                    break

                received_text += received_bytes.decode(errors="replace")
                while "\n" in received_text:
                    text_line, received_text = received_text.split("\n", 1)
                    text_line = text_line.strip()
                    if text_line:
                        self.when_text_line_arrives(text_line)
        except OSError:
            pass
        finally:
            self.is_connected = False

    def read_audio_packets_from_server_forever(self, voice_socket):
        last_name_send_time = time.monotonic()

        while self.voice_socket is voice_socket:
            try:
                audio_bytes = voice_socket.recvfrom(65535)[0]
            except socket.timeout:
                seconds_since_last_name_send = time.monotonic() - last_name_send_time
                if seconds_since_last_name_send > SEND_NAME_TO_VOICE_SERVER_EVERY_SECONDS:
                    self.send_name_to_voice_server()
                    last_name_send_time = time.monotonic()
                continue
            except OSError:
                break

            if len(audio_bytes) < 2 or len(audio_bytes) % 2 != 0:
                continue

            audio_samples = numpy.frombuffer(audio_bytes, dtype=numpy.int16).copy()
            self.when_audio_samples_arrive(audio_samples)



class HarmonyTaskSender:
    """Sends a computer task to the Harmony server."""

    def __init__(self, api_host=HARMONY_API_HOST, api_port=HARMONY_API_PORT, agent_id=None):
        self.api_host = api_host
        self.api_port = api_port
        self.agent_id = agent_id

    def send_task_to_harmony(self, task_text):
        request_data = {"action": "send_task", "task": task_text}
        if self.agent_id:
            request_data["agent_id"] = self.agent_id

        request_bytes = json.dumps(request_data).encode()

        try:
            with socket.create_connection((self.api_host, self.api_port), timeout=5) as api_socket:
                api_socket.sendall(len(request_bytes).to_bytes(8, "big") + request_bytes)

                response_header = api_socket.recv(8)
                if len(response_header) < 8:
                    return False

                response_length = int.from_bytes(response_header, "big")
                response_bytes = b""

                while len(response_bytes) < response_length:
                    next_chunk = api_socket.recv(response_length - len(response_bytes))
                    if not next_chunk:
                        break
                    response_bytes += next_chunk

            response_data = json.loads(response_bytes.decode())
            return bool(response_data.get("success"))
        except (OSError, ValueError):
            return False



class FinishedSpeechBuffer:
    """Collects audio until a person has finished one sentence or command."""

    def __init__(self):
        self.audio_parts = []
        self.speech_sample_count = 0
        self.silence_sample_count = 0

    def add_audio_from_call(self, audio_samples):
        audio_volume = 0.0
        if audio_samples.size:
            audio_volume = float(numpy.sqrt(numpy.mean(audio_samples.astype(numpy.float32) ** 2)))

        self.audio_parts.append(audio_samples)

        if audio_volume >= SILENCE_VOLUME_LEVEL:
            self.speech_sample_count += audio_samples.size
            self.silence_sample_count = 0
        else:
            self.silence_sample_count += audio_samples.size

    def has_finished_speech(self):
        has_enough_voice = self.speech_sample_count >= MINIMUM_SPEECH_SECONDS * CALL_AUDIO_SAMPLE_RATE
        has_enough_silence = self.silence_sample_count >= SILENCE_SECONDS_THAT_FINISH_SPEECH * CALL_AUDIO_SAMPLE_RATE
        return has_enough_voice and has_enough_silence

    def take_finished_speech(self):
        if self.audio_parts:
            audio_samples = numpy.concatenate(self.audio_parts)
        else:
            audio_samples = numpy.zeros(0, dtype=numpy.int16)

        self.audio_parts = []
        self.speech_sample_count = 0
        self.silence_sample_count = 0

        return audio_samples



def text_has_wake_word(text):
    return WAKE_WORD_PATTERN.search(text) is not None


def task_text_after_wake_word(text):
    wake_word_matches = list(WAKE_WORD_PATTERN.finditer(text))

    for wake_word_match in reversed(wake_word_matches):
        possible_task_text = fix_heard_task_start(text[wake_word_match.end():].strip(" ,:.-"))
        possible_task_lower_text = possible_task_text.lower()

        for task_start_word in TASK_START_WORDS:
            is_exact_task_start = possible_task_lower_text == task_start_word
            starts_with_task_start = possible_task_lower_text.startswith(task_start_word + " ")
            if is_exact_task_start or starts_with_task_start:
                return possible_task_text

    return ""


def fix_heard_task_start(text):
    words = text.strip().split(maxsplit=1)
    if not words:
        return ""

    first_word = words[0].lower().strip(" ,:.-")
    better_first_word = HEARD_TASK_START_FIXES.get(first_word)
    if not better_first_word:
        return text.strip()

    if len(words) == 1:
        return better_first_word

    return f"{better_first_word} {words[1].strip()}"


def has_request_besides_wake_word(text):
    text_without_wake_words = WAKE_WORD_PATTERN.sub(" ", text)
    useful_words = [
        word
        for word in re.findall(r"[a-z0-9]+", text_without_wake_words.lower())
        if word not in {"hey", "hi", "hello", "please", "ok", "okay"}
    ]
    return len(useful_words) > 0


def task_key(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def text_sounds_like_task_reply_without_task(text):
    clean_text = text.lower().strip()
    return any(clean_text.startswith(word) for word in TASK_REPLY_WORDS)


def load_speech_tools_from_computer():
    return LocalSpeechTools(
        text_to_speech_voice=os.environ.get("AIRVOICE_TTS_VOICE", TEXT_TO_SPEECH_VOICE),
        text_to_speech_rate=os.environ.get("AIRVOICE_TTS_RATE", TEXT_TO_SPEECH_RATE),
        speech_to_text_language=os.environ.get("AIRVOICE_STT_LANGUAGE", "en-US"),
    )



class AirvoiceAgentBrain:
    """Owns the full AirVoice agent workflow."""

    def __init__(self, server_host, username, password, model_name, agent_id=None):
        self.server_host = server_host
        self.username = username
        self.password = password
        self.model_name = model_name
        self.agent_id = agent_id
        self.system_prompt = VOICE_DECISION_PROMPT.format(name=username)

        self.recent_heard_lines = []
        self.is_inside_call = False
        self.is_speaking_now = False
        self.ignore_call_audio_until = 0.0
        self.last_sent_task_key = ""
        self.last_sent_task_time = 0.0
        self.finished_speech_buffer = FinishedSpeechBuffer()
        self.audio_lock = threading.Lock()
        self.speak_lock = threading.Lock()

        ollama_api_key = config.OLLAMA_API_KEY
        if not ollama_api_key:
            raise RuntimeError("OLLAMA_API_KEY not found")

        self.ollama_client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {ollama_api_key}"},
        )

        self.speech_tools = load_speech_tools_from_computer()
        self.task_sender = HarmonyTaskSender(agent_id=agent_id)
        self.airvoice_connection = AirvoiceServerConnection(
            server_host,
            username,
            password,
            when_text_line_arrives=self.handle_text_line_from_airvoice_server,
            when_audio_samples_arrive=self.handle_audio_samples_from_airvoice_call,
        )

    def run(self):
        try:
            self.airvoice_connection.connect_to_server()
        except OSError as error:
            print(f"[Airvoice] Cannot reach {self.server_host}:{AIRVOICE_SERVER_PORT}: {error}")
            remove_brain_from_active_list(self.agent_id)
            return

        self.airvoice_connection.send_text_line(f"REGISTER {self.username} {self.password}")
        self.airvoice_connection.send_text_line(f"LOGIN {self.username} {self.password}")
        print(f"[Airvoice] Connected to {self.server_host} as {self.username}")

        try:
            while self.airvoice_connection.is_connected:
                time.sleep(0.2)
                self.listen_for_finished_speech()
        except Exception as error:
            print(f"[Airvoice] Error: {error}")
        finally:
            self.airvoice_connection.close_connection()
            remove_brain_from_active_list(self.agent_id)

    def stop(self):
        self.airvoice_connection.send_text_line("QUIT")
        self.airvoice_connection.close_connection()

    def handle_text_line_from_airvoice_server(self, text_line):
        text_parts = text_line.split()
        server_command = text_parts[0].upper() if text_parts else ""
        command_words = text_parts[1:]

        if server_command == "OK":
            print(f"[Airvoice] Logged in as {self.username}")
            return

        if server_command == "ERR":
            print(f"[Airvoice] Server: ERR {' '.join(command_words)}")
            return

        if server_command == "INCOMING" and command_words:
            caller_name = command_words[0]
            self.airvoice_connection.send_text_line(f"ACCEPT {caller_name}")
            return

        if server_command == "CALL_START" and command_words:
            try:
                self.airvoice_connection.open_voice_stream(int(command_words[0]))
            except ValueError:
                pass
            return

        if server_command == "PARTICIPANTS":
            self.is_inside_call = True
            print(f"[Airvoice] In call with: {' '.join(command_words)}")
            return

        if server_command in ("CALL_ENDED", "HANGUP_OK"):
            self.is_inside_call = False
            with self.audio_lock:
                self.finished_speech_buffer = FinishedSpeechBuffer()

    def handle_audio_samples_from_airvoice_call(self, audio_samples):
        if not self.is_inside_call:
            return

        if self.is_speaking_now:
            return

        if time.monotonic() < self.ignore_call_audio_until:
            return

        with self.audio_lock:
            self.finished_speech_buffer.add_audio_from_call(audio_samples)

    def listen_for_finished_speech(self):
        with self.audio_lock:
            if not self.finished_speech_buffer.has_finished_speech():
                return
            audio_samples = self.finished_speech_buffer.take_finished_speech()

        heard_text = self.speech_tools.turn_heard_audio_into_text(audio_samples).strip()
        if not heard_text:
            return

        print(f"[Airvoice] Heard: {heard_text!r}")

        if not text_has_wake_word(heard_text):
            return

        self.answer_heard_text(heard_text)

    def answer_heard_text(self, heard_text):
        self.recent_heard_lines = (self.recent_heard_lines + [heard_text])[-RECENT_LINES_TO_REMEMBER:]

        direct_task_text = task_text_after_wake_word(heard_text)
        if direct_task_text:
            print(f"[Airvoice] Fast command: {direct_task_text!r}")
            if self.should_ignore_repeated_task(direct_task_text):
                print(f"[Airvoice] Ignored repeated task: {direct_task_text}")
                return

            did_send_task = self.task_sender.send_task_to_harmony(direct_task_text)
            print(f"[Airvoice] Task {'sent' if did_send_task else 'failed'}: {direct_task_text}")
            if did_send_task:
                self.remember_sent_task(direct_task_text)
                self.start_task_result_recap(direct_task_text)
                clean_task_text = self.clean_recap_sentence(direct_task_text).rstrip(".")
                if clean_task_text:
                    self.speak_text_to_airvoice_call(f"Starting {clean_task_text}.")
            else:
                self.speak_text_to_airvoice_call("I could not send that to the agent.")
            return

        if not has_request_besides_wake_word(heard_text):
            print("[Airvoice] Ignored bare wake word")
            return

        print(f"[Airvoice] Thinking ({self.model_name})...")
        decision = self.ask_model_what_to_say_or_do(heard_text)
        if not decision:
            return

        text_to_say = str(decision.get("say", "")).strip()
        task_text = str(decision.get("task", "")).strip()

        print(f"[Airvoice] Decision: say={text_to_say!r}, task={task_text!r}")

        if task_text:
            if self.should_ignore_repeated_task(task_text):
                print(f"[Airvoice] Ignored repeated task: {task_text}")
                return
            else:
                did_send_task = self.task_sender.send_task_to_harmony(task_text)
                print(f"[Airvoice] Task {'sent' if did_send_task else 'failed'}: {task_text}")
                if did_send_task:
                    self.remember_sent_task(task_text)
                    self.start_task_result_recap(task_text)
                else:
                    text_to_say = text_to_say or "I could not send that to the agent."

        if not task_text and text_sounds_like_task_reply_without_task(text_to_say):
            print("[Airvoice] Ignored action reply without task")
            return

        if text_to_say:
            self.speak_text_to_airvoice_call(text_to_say)

    def should_ignore_repeated_task(self, task_text):
        current_task_key = task_key(task_text)
        if not current_task_key:
            return False

        seconds_since_last_task = time.monotonic() - self.last_sent_task_time
        return (
            current_task_key == self.last_sent_task_key
            and seconds_since_last_task < DUPLICATE_TASK_IGNORE_SECONDS
        )

    def remember_sent_task(self, task_text):
        self.last_sent_task_key = task_key(task_text)
        self.last_sent_task_time = time.monotonic()

    def ask_model_what_to_say_or_do(self, heard_text):
        recent_lines_text = "\n".join(f"- {line}" for line in self.recent_heard_lines)
        user_prompt = (
            "Recent meeting lines:\n"
            f"{recent_lines_text}\n\n"
            f"Current line: {heard_text}\n"
            "Decide what to say now."
        )

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
                options=MODEL_OPTIONS,
            )
        except Exception as error:
            print(f"[Airvoice] AI error: {error}")
            return {}

        raw_model_text = (response.get("message", {}).get("content") or "").strip()

        return read_json_object_from_text(raw_model_text) or {}

    def start_task_result_recap(self, task_text):
        task_queued_time = time.time()
        threading.Thread(
            target=self.wait_for_task_result_and_speak_recap,
            args=(task_text, task_queued_time),
            daemon=True,
        ).start()

    def wait_for_task_result_and_speak_recap(self, task_text, task_queued_time):
        if not self.agent_id:
            return

        stop_waiting_time = time.monotonic() + TASK_RESULT_MAX_WAIT_SECONDS
        saw_agent_working_on_task = False
        last_agent_row = None

        while time.monotonic() < stop_waiting_time and self.airvoice_connection.is_connected:
            agent_row = db.get_agent(self.agent_id)
            if not agent_row:
                break

            last_agent_row = agent_row
            agent_task = (agent_row.get("task") or "").strip()
            agent_status = (agent_row.get("status") or "").strip()
            agent_updated_time = float(agent_row.get("updated_at") or 0)

            if agent_task == task_text and agent_status == "working":
                saw_agent_working_on_task = True

            if agent_task == task_text and agent_status == "idle" and agent_updated_time >= task_queued_time:
                recap_text = self.build_task_result_recap(task_text, agent_row)
                self.speak_recap_if_still_in_call(recap_text)
                return

            if saw_agent_working_on_task and agent_status != "working":
                recap_text = self.build_task_result_recap(task_text, agent_row)
                self.speak_recap_if_still_in_call(recap_text)
                return

            time.sleep(TASK_RESULT_CHECK_SECONDS)

        if saw_agent_working_on_task and last_agent_row:
            recap_text = self.build_task_result_recap(task_text, last_agent_row)
            self.speak_recap_if_still_in_call(recap_text)

    def build_task_result_recap(self, task_text, agent_row):
        agent_status = (agent_row.get("status") or "").strip()
        status_text = (agent_row.get("status_text") or "").strip()

        if agent_status == "disconnected":
            return self.create_task_problem_recap(
                task_text,
                "the agent disconnected before finishing",
            )

        if status_text.startswith("AI error"):
            return self.create_task_problem_recap(
                task_text,
                "the AI call failed before finishing",
            )

        step = {}
        if agent_row.get("step_json"):
            try:
                step = json.loads(agent_row["step_json"])
            except (TypeError, ValueError):
                step = {}

        recap_text = self.create_task_result_recap_with_model(task_text, agent_status, status_text, step)
        if recap_text:
            return recap_text

        return "The task ended, but I do not have details."

    def create_task_result_recap_with_model(self, task_text, agent_status, status_text, step):
        status_short = self.clean_recap_note(step.get("status_short") or status_text)
        reasoning_note = self.clean_recap_note(step.get("reasoning") or "", max_chars=260)
        action = self.clean_recap_note(step.get("action") or "")
        value = self.clean_recap_note(step.get("value") or "")
        command_output = self.clean_recap_note(step.get("cmd_output") or "")

        has_grounding = any([reasoning_note, status_short, action, value, command_output, status_text])
        if not has_grounding:
            return "The task ended, but I do not have details."

        prompt = (
            "Write one short spoken recap for a call after a computer task.\n"
            "Sound like a helpful colleague, not a report.\n"
            "Do not say 'quick update'. Do not say 'I finished that'.\n"
            "Base the recap on Last reasoning first.\n"
            "Use status, action, value, and command output only to clarify the reasoning.\n"
            "Do not invent facts, apps, files, websites, results, or success.\n"
            "Do not claim success unless the facts below say it succeeded.\n"
            "Do not quote the reasoning word for word.\n"
            "Use 6 to 14 words. Return JSON only: {\"say\": \"...\"}\n\n"
            f"Requested task: {task_text}\n"
            f"Agent status: {agent_status}\n"
            f"Status text: {status_text}\n"
            f"Last short status: {status_short}\n"
            f"Last reasoning: {reasoning_note}\n"
            f"Last action: {action}\n"
            f"Last value: {value}\n"
            f"Command output if any: {command_output}"
        )
        return self.ask_model_for_short_spoken_line(
            prompt,
            default_text="The task ended, but I do not have details.",
            model_options=RECAP_SPOKEN_LINE_OPTIONS,
        )

    def create_task_problem_recap(self, task_text, problem_text):
        prompt = (
            "Write one short spoken line for a call about a computer task that did not finish.\n"
            "Sound natural and direct.\n"
            "Do not say 'quick update'. Do not say 'I finished that'.\n"
            "Use 6 to 12 words. Return JSON only: {\"say\": \"...\"}\n\n"
            f"Requested task: {task_text}\n"
            f"Problem: {problem_text}"
        )
        return self.ask_model_for_short_spoken_line(
            prompt,
            default_text=f"I could not finish it because {problem_text}.",
        )

    def ask_model_for_short_spoken_line(self, prompt, default_text="", model_options=None):
        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You write short natural voice-call lines."},
                    {"role": "user", "content": prompt},
                ],
                format="json",
                options=model_options or SHORT_SPOKEN_LINE_OPTIONS,
            )
        except Exception as error:
            print(f"[Airvoice] Spoken line AI error: {error}")
            return default_text

        raw_model_text = (response.get("message", {}).get("content") or "").strip()
        spoken_line = read_json_object_from_text(raw_model_text) or {}
        return self.clean_spoken_line(spoken_line.get("say") or default_text)

    def clean_spoken_line(self, text):
        clean_text = " ".join(str(text).split()).strip(" \"'")
        if not clean_text:
            return ""

        generic_starts = (
            "quick update:",
            "quick update,",
            "quick update -",
            "i finished that:",
            "i finished that,",
            "i finished that -",
            "i'll do that.",
            "i will do that.",
        )
        lower_clean_text = clean_text.lower()

        for generic_start in generic_starts:
            if lower_clean_text.startswith(generic_start):
                clean_text = clean_text[len(generic_start):].strip()
                lower_clean_text = clean_text.lower()

        clean_text = clean_text[:160].rstrip(" ,;:")
        if clean_text and clean_text[-1] not in ".!?":
            clean_text += "."
        return clean_text

    def clean_recap_note(self, text, max_chars=120):
        return " ".join(str(text).split())[:max_chars]

    def clean_recap_sentence(self, text):
        clean_text = " ".join(str(text).split())
        if not clean_text:
            return ""

        clean_text = clean_text[:220].rstrip(" ,;:")
        if clean_text[-1] not in ".!?":
            clean_text += "."
        return clean_text

    def speak_recap_if_still_in_call(self, recap_text):
        if not recap_text:
            return

        if not self.is_inside_call or not self.airvoice_connection.is_connected:
            return

        self.speak_text_to_airvoice_call(recap_text)

    def speak_text_to_airvoice_call(self, text_to_say):
        with self.speak_lock:
            self.is_speaking_now = True
            with self.audio_lock:
                self.finished_speech_buffer = FinishedSpeechBuffer()

            try:
                audio_samples = self.speech_tools.turn_text_into_call_audio(text_to_say)
                if audio_samples.size == 0:
                    print("[Airvoice] TTS returned no audio")
                    return

                print(f"[Airvoice] Speaking {audio_samples.size / CALL_AUDIO_SAMPLE_RATE:.2f}s")

                send_start_time = time.monotonic()
                audio_packet_number = 0

                for start_sample_index in range(0, audio_samples.size, AUDIO_SAMPLES_PER_PACKET):
                    audio_packet = audio_samples[start_sample_index:start_sample_index + AUDIO_SAMPLES_PER_PACKET]

                    if audio_packet.size < AUDIO_SAMPLES_PER_PACKET:
                        padded_audio_packet = numpy.zeros(AUDIO_SAMPLES_PER_PACKET, dtype=numpy.int16)
                        padded_audio_packet[:audio_packet.size] = audio_packet
                        audio_packet = padded_audio_packet

                    send_time = send_start_time + audio_packet_number * AUDIO_PACKET_SECONDS
                    seconds_until_send_time = send_time - time.monotonic()
                    if seconds_until_send_time > 0:
                        time.sleep(seconds_until_send_time)

                    self.airvoice_connection.send_audio_to_call(audio_packet)
                    audio_packet_number += 1
            finally:
                self.ignore_call_audio_until = time.monotonic() + IGNORE_CALL_AUDIO_AFTER_SPEAKING_SECONDS
                with self.audio_lock:
                    self.finished_speech_buffer = FinishedSpeechBuffer()
                self.is_speaking_now = False



active_brains = {}
active_brains_lock = threading.Lock()


def remove_brain_from_active_list(agent_id):
    with active_brains_lock:
        active_brains.pop(agent_id, None)


def enable(agent_id, host=None, username=None, password=None, model=None):
    with active_brains_lock:
        if agent_id in active_brains:
            return True

    server_host = host or os.environ.get("AIRVOICE_HOST", "127.0.0.1")
    username = username or os.environ.get("AIRVOICE_USER_PREFIX", "") + agent_id
    password = password or os.environ.get("AIRVOICE_PASS", "harmony")
    model_name = (
        model
        or os.environ.get("AIRVOICE_FAST_MODEL")
        or os.environ.get("AIRVOICE_MODEL", DEFAULT_MODEL_NAME)
    )

    brain = AirvoiceAgentBrain(
        server_host,
        username,
        password,
        model_name,
        agent_id=agent_id,
    )

    with active_brains_lock:
        if agent_id in active_brains:
            return True
        active_brains[agent_id] = brain

    threading.Thread(target=brain.run, daemon=True).start()
    print(f"[Airvoice] Enabled for {agent_id} ({username}@{server_host})")
    return True


def disable(agent_id):
    with active_brains_lock:
        brain = active_brains.pop(agent_id, None)

    if not brain:
        return False

    try:
        brain.stop()
    except Exception:
        pass

    print(f"[Airvoice] Disabled for {agent_id}")
    return True


def is_enabled(agent_id):
    with active_brains_lock:
        return agent_id in active_brains


def enabled_ids():
    with active_brains_lock:
        return set(active_brains.keys())
