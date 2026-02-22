const REPO_ARCHIVE_BASE = "https://github.com/danielreiman/Harmony/archive/refs/heads/";
const installPicker = document.querySelector("[data-install-picker]");
const installToggle = document.getElementById("install-toggle");
const installToggleText = document.querySelector(".install-toggle-text");
const installOptions = document.querySelectorAll(".install-option");
const instructionsButton = document.getElementById("instructions-btn");
const customAlert = document.getElementById("custom-alert");
const customAlertMessage = document.querySelector(".custom-alert-message");
const customAlertClose = document.getElementById("custom-alert-close");
const BRANCH_LABELS = {
  main: "Stable (main)",
  "in-development": "In Development",
};
let alertTimerId = null;

const refreshIcons = () => {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }
};

const hideCustomAlert = () => {
  if (!customAlert) return;
  customAlert.classList.remove("is-visible");
  window.setTimeout(() => {
    if (!customAlert.classList.contains("is-visible")) {
      customAlert.hidden = true;
    }
  }, 180);
};

const showCustomAlert = (message) => {
  if (!customAlert || !customAlertMessage) return;
  customAlertMessage.textContent = message;
  customAlert.hidden = false;
  window.requestAnimationFrame(() => {
    customAlert.classList.add("is-visible");
  });
  if (alertTimerId) {
    window.clearTimeout(alertTimerId);
  }
  alertTimerId = window.setTimeout(hideCustomAlert, 4200);
  refreshIcons();
};

if (installPicker && installToggle && installToggleText && installOptions.length > 0) {
  const setOpen = (open) => {
    installPicker.dataset.open = open ? "true" : "false";
    installToggle.setAttribute("aria-expanded", open ? "true" : "false");
  };

  const setSelectedBranch = (branch) => {
    installOptions.forEach((option) => {
      const isSelected = option.dataset.branch === branch;
      option.classList.toggle("is-selected", isSelected);
      option.setAttribute("aria-selected", isSelected ? "true" : "false");
    });
    const label = BRANCH_LABELS[branch] || branch;
    installToggleText.textContent = `Install Now - ${label}`;
    refreshIcons();
  };

  installToggle.addEventListener("click", () => {
    const isOpen = installPicker.dataset.open === "true";
    setOpen(!isOpen);
  });

  installOptions.forEach((option) => {
    option.addEventListener("click", () => {
      const branch = option.dataset.branch;
      if (!branch) return;
      setSelectedBranch(branch);
      setOpen(false);
      window.location.assign(`${REPO_ARCHIVE_BASE}${branch}.zip`);
    });
  });

  document.addEventListener("click", (event) => {
    if (!installPicker.contains(event.target)) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
  });

  setSelectedBranch("main");
  setOpen(false);
}

if (instructionsButton) {
  instructionsButton.addEventListener("click", () => {
    showCustomAlert("Instructions book is coming soon. The developer is working on it.");
  });
}

if (customAlertClose) {
  customAlertClose.addEventListener("click", hideCustomAlert);
}

refreshIcons();
