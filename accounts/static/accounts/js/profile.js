document.addEventListener("DOMContentLoaded", () => {
  const profilePictureInput = document.getElementById("profile-picture-input");
  const chooseFileBtn = document.getElementById("choose-file-btn");
  const takePhotoBtn = document.getElementById("take-photo-btn");

  if (profilePictureInput) {
    profilePictureInput.addEventListener("change", handleProfilePictureUpload);
  }

  if (chooseFileBtn) {
    chooseFileBtn.addEventListener("click", () => {
      profilePictureInput.removeAttribute("capture");
      profilePictureInput.click();
    });
  }

  if (takePhotoBtn) {
    takePhotoBtn.addEventListener("click", () => {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        profilePictureInput.setAttribute("capture", "environment");
        profilePictureInput.click();
      } else {
        showError("Camera access is not supported on this device or browser.");
      }
    });
  }
});

function handleProfilePictureUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  // Validate file size (10MB max)
  if (file.size > 10 * 1024 * 1024) {
    showError("File size too large. Maximum size is 10MB.");
    return;
  }

  // Validate file type
  if (!file.type.startsWith("image/")) {
    showError("Please select an image file.");
    return;
  }

  const formData = new FormData();
  formData.append("profile_picture", file);
  formData.append("csrfmiddlewaretoken", document.querySelector("[name=csrfmiddlewaretoken]").value);

  // Show loading state
  const profilePicture = document.querySelector(".profile-picture");
  const loadingSpinner = document.getElementById("loading-spinner");
  if (profilePicture) {
    profilePicture.style.opacity = "0.5";
  }
  if (loadingSpinner) {
    loadingSpinner.classList.remove("hidden");
  }

  fetch(window.location.href, {
    method: "POST",
    body: formData,
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      if (data.status === "success") {
        // Update profile picture
        if (data.profile_picture_url) {
          updateProfilePicture(data.profile_picture_url);
        }
        showSuccess("Profile picture updated successfully");
      } else {
        throw new Error(data.message || "Error updating profile picture");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showError(error.message || "Error updating profile picture");
    })
    .finally(() => {
      // Reset loading state
      if (profilePicture) {
        profilePicture.style.opacity = "1";
      }
      if (loadingSpinner) {
        loadingSpinner.classList.add("hidden");
      }
    });
}

function updateProfilePicture(imageUrl) {
  const profilePicture = document.querySelector(".profile-picture");
  if (profilePicture) {
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    profilePicture.src = `${imageUrl}?t=${timestamp}`;
  }
}

function showError(message) {
  const toast = createToast(message, "error");
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function showSuccess(message) {
  const toast = createToast(message, "success");
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function createToast(message, type) {
  const toast = document.createElement("div");
  toast.className = `fixed top-4 right-4 p-4 rounded-md text-white ${
    type === "error" ? "bg-red-500" : "bg-green-500"
  } z-50`;
  toast.textContent = message;
  return toast;
}