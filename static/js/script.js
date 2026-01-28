const urlInput = document.getElementById("urlInput");
const extractBtn = document.getElementById("extractBtn");
const loading = document.getElementById("loading");
const results = document.getElementById("results");
const videoInfo = document.getElementById("videoInfo");
const formatList = document.getElementById("formatList");
const clearInputIcon = document.getElementById("clearInputIcon");

function isValidYouTubeUrl(url) {
  const regex =
    /^(https?:\/\/)?(www\.)?(youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)[a-zA-Z0-9_-]{11}/;
  return regex.test(url);
}

function extractVideoId(url) {
  const match = url.match(
    /(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/
  );
  return match ? match[1] : null;
}

function showLoading() {
  loading.style.display = "block";
  results.style.display = "none";
  extractBtn.disabled = true;
  extractBtn.textContent = "Analyzing...";
}

function hideLoading() {
  loading.style.display = "none";
  extractBtn.disabled = false;
  extractBtn.textContent = "Analyze Video";
}

// Displays the results fetched from the server, including video info and format lists.
function displayResults(data) {
  // Store formats globally for easy access by playVideo and downloadVideo functions without re-fetching.
  // This avoids passing around large data structures or querying the DOM repeatedly.
  window.currentFormats = data.formats;
  window.currentVideoTitle = data.title; // Store video title globally
  window.currentVideoDuration = data.duration_seconds || 0; // Store duration for FFmpeg progress

  if (urlInput.value.trim() !== "" && clearInputIcon) {
    clearInputIcon.style.display = "block";
  }

  // --- START: Thumbnail Handling ---
  const thumbnailImg = document.getElementById("videoThumbnail");
  if (data.thumbnail_url) {
    thumbnailImg.src = data.thumbnail_url;
    thumbnailImg.style.display = "block";
  } else {
    thumbnailImg.style.display = "none";
    thumbnailImg.src = ""; // Clear src if no thumbnail
  }
  // --- END: Thumbnail Handling ---

  // Clear previous text info (but not the thumbnail image)
  let textInfoDiv = videoInfo.querySelector(".video-text-details");
  if (textInfoDiv) {
    textInfoDiv.remove();
  }

  textInfoDiv = document.createElement("div");
  textInfoDiv.className = "video-text-details"; // Add a class for potential styling
  textInfoDiv.innerHTML = `
          <div class="video-title">${data.title}</div>
          <div class="video-meta">
              Duration: ${data.duration} | Views: ${data.view_count} | 
              Uploaded: ${data.upload_date} | Channel: ${data.uploader}
          </div>
      `;
  videoInfo.appendChild(textInfoDiv); // Append new text info

  // Clear format list
  formatList.innerHTML = "";

  // Group formats by type
  const videoAudioFormats = data.formats.filter(
    (f) => f.type === "video+audio"
  );
  const videoOnlyFormats = data.formats.filter((f) => f.type === "video-only");
  const audioOnlyFormats = data.formats.filter((f) => f.type === "audio-only");
  const otherFormats = data.formats.filter((f) => f.type === "other");

  // Add Combined High Quality section FIRST (most useful)
  if (videoOnlyFormats.length > 0 && audioOnlyFormats.length > 0) {
    addCombinedSection(videoOnlyFormats, audioOnlyFormats);
  }

  // Add Video + Audio section
  if (videoAudioFormats.length > 0) {
    addSectionHeader(
      "🎬 Video + Audio (Direct Download)",
      "#27ae60",
      "video-audio"
    );
    videoAudioFormats.forEach((format) => addFormatItem(format, "video-audio"));
  }

  // Add Video Only section
  if (videoOnlyFormats.length > 0) {
    addSectionHeader("📹 Video Only", "#e67e22", "video-only");
    videoOnlyFormats.forEach((format) => addFormatItem(format, "video-only"));
  }

  // Add Audio Only section
  if (audioOnlyFormats.length > 0) {
    addSectionHeader("🎵 Audio Only", "#9b59b6", "audio-only");
    audioOnlyFormats.forEach((format) => addFormatItem(format, "audio-only"));
  }

  // Add Other formats if any
  if (otherFormats.length > 0) {
    addSectionHeader("❓ Other Formats", "#95a5a6", "other");
    otherFormats.forEach((format) => addFormatItem(format, "other"));
  }

  results.style.display = "block";
}

// Adds a special section for 'High Quality Combined' downloads.
// This allows users to combine the best available audio with selected video-only streams.
function addCombinedSection(videoFormats, audioFormats) {
  addSectionHeader(
    "⚡ High Quality Combined (Best Choice)",
    "#8e44ad",
    "high-quality"
  );

  // Get best audio format for combining
  // Assumes audioFormats is already sorted by quality (best first) by the server.
  const bestAudio = audioFormats[0];

  // Create combination options using the video-only formats provided by the server.
  // (These are typically pre-filtered for reasonable quality, e.g., >=480p, on the server-side).
  const topVideoFormats = videoFormats; // Use all video formats provided by the server (already filtered >= 480p)

  topVideoFormats.forEach((videoFormat, index) => {
    const combinedItem = document.createElement("div");
    combinedItem.className = "format-item";
    combinedItem.style.background = "linear-gradient(135deg, #f8f9fa, #e9ecef)";
    combinedItem.style.border = "2px solid #8e44ad22";

    // Use the actual video format quality, not hardcoded
    const videoQualityDisplay = `${
      videoFormat.quality || videoFormat.height + "p" || "Unknown Video"
    }`;
    const codecInfo = `Video: ${videoFormat.width || "?"}x${
      videoFormat.height || "?"
    } + Best Available Audio`;

    const qualityText = `${
      videoFormat.quality || videoFormat.height + "p" || "Unknown"
    } + Best Audio`;
    combinedItem.innerHTML = `
    <div class="format-item-content">
        <div class="format-details">
            <div class="format-type">⚡ ${videoQualityDisplay} + Best Audio (MP4) [Format ${videoFormat.format_id}]</div>
            <div class="format-specs">${codecInfo}</div>
        </div>
        <div style="display: flex; gap: 8px;">
            <button class="download-btn" style="background: linear-gradient(135deg, #a569bd, #8e44ad);">
                ⚡ Combine & Download
            </button>
        </div>
    </div>
    <div class="progress-container" style="display: none;">
        <div class="phase-item" data-phase="video">
            <span class="phase-icon">⏳</span>
            <span class="phase-label">Video:</span>
            <span class="phase-status">Waiting...</span>
            <div class="progress-bar-bg" style="display: none;">
                <div class="progress-bar-fill" style="width: 0%"></div>
            </div>
        </div>
        <div class="phase-item" data-phase="audio">
            <span class="phase-icon">⏳</span>
            <span class="phase-label">Audio:</span>
            <span class="phase-status">Waiting...</span>
            <div class="progress-bar-bg" style="display: none;">
                <div class="progress-bar-fill" style="width: 0%"></div>
            </div>
        </div>
        <div class="phase-item" data-phase="combining">
            <span class="phase-icon">⏳</span>
            <span class="phase-label">Combining:</span>
            <span class="phase-status">Waiting...</span>
            <div class="progress-bar-bg" style="display: none;">
                <div class="progress-bar-fill" style="width: 0%"></div>
            </div>
        </div>
    </div>
`;

    formatList.appendChild(combinedItem);

    // Add event listener to the button after it's created and appended
    const button = combinedItem.querySelector(".download-btn");
    const progressContainer = combinedItem.querySelector(".progress-container");
    button.progressContainer = progressContainer; // Store reference for easy access

    // Store original text and background ONCE when button is created
    button.originalText = button.textContent;
    button.originalBackground = button.style.background;

    // Use onclick instead of addEventListener for consistent handler replacement
    button.onclick = function () {
      combineVideoAudio(videoFormat, bestAudio, this);
    };
  });
}

async function combineVideoAudio(
  videoFormat, // Full video format object
  audioFormat, // Full audio format object
  buttonElement
  // videoTitle can be accessed via window.currentVideoTitle
) {
  // Clear any previous cancellation flag
  buttonElement.taskCancelled = false;
  buttonElement.cancelHandlerAttached = false;

  // This function calls the server's /combine endpoint to get a merged video and audio file.
  try {
    const currentUrl = urlInput.value.trim();

    const button =
      buttonElement || (typeof event !== "undefined" ? event.target : null);
    if (!button) {
      console.error("Button element not found");
      return;
    }

    // Show queued state immediately
    initializeQueuedState(button, true); // true = multi-phase progress

    // Request combination from server
    // Request the server to combine the specified video and audio formats.
    // Call the /combine endpoint. Expects a JSON response with task_id and status_url.
    const response = await fetch("/combine", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: currentUrl,
        video_format_details: videoFormat,
        audio_format_details: audioFormat,
        videoTitle: window.currentVideoTitle || "video",
        videoDuration: window.currentVideoDuration || 0,
        // videoResolution and videoVcodec are now part of video_format_details
        // audioAcodec and extensions are now part of their respective details objects
      }),
    });

    if (response.ok) {
      // Attempt to parse the filename from the 'Content-Disposition' header.
      // This header can have different formats, so we try to handle common ones.
      let filename = "combined_video.mp4";

      try {
        const contentDisposition = response.headers.get("Content-Disposition");
        if (contentDisposition) {
          // Handle both old and new (UTF-8) header formats
          if (contentDisposition.includes("filename*=UTF-8''")) {
            const parts = contentDisposition.split("filename*=UTF-8''");
            if (parts.length > 1) {
              filename = decodeURIComponent(parts[1]);
            }
          } else if (contentDisposition.includes("filename=")) {
            const parts = contentDisposition.split("filename=");
            if (parts.length > 1) {
              filename = parts[1].replace(/"/g, "");
            }
          }
        }
      } catch (headerError) {
        console.error("Error parsing filename from headers:", headerError);
        // Keep default filename
      }

      // The /combine endpoint returns JSON with a task_id for polling, not the file directly.
      const result = await response.json();

      // Attach cancel handler immediately (works for both queued and processing)
      attachCancelHandler(button, result.task_id, () =>
        combineVideoAudio(videoFormat, audioFormat, button)
      );

      // Start polling for task status
      pollTaskStatus(
        result.status_url,
        button,
        button.originalText,
        result.task_id,
        () => combineVideoAudio(videoFormat, audioFormat, button), // Pass the full objects for retry
        "combine" // Add buttonType
      );
    } else {
      const error = await response.json();
      alert("Combination failed: " + (error.error || "Unknown error"));
      // Restore button if initial queuing failed
      restoreButtonState(button);
      toggleProgressContainer(button, false);
    }
  } catch (error) {
    console.error("Combination error:", error);
    alert("Combination failed: " + error.message);
    // Restore button if an unexpected error occurs
    restoreButtonState(buttonElement);
    toggleProgressContainer(buttonElement, false);
  }
}

// --- Helper Functions for Button State Management ---

// Show custom cancel confirmation modal
function showCancelConfirmation() {
  return new Promise((resolve) => {
    // Create modal if it doesn't exist
    let modalOverlay = document.getElementById("cancelModal");
    if (!modalOverlay) {
      modalOverlay = document.createElement("div");
      modalOverlay.id = "cancelModal";
      modalOverlay.className = "modal-overlay";
      modalOverlay.innerHTML = `
        <div class="modal-dialog">
          <div class="modal-title">Cancel Download?</div>
          <div class="modal-message">Are you sure you want to cancel this download?</div>
          <div class="modal-buttons">
            <button class="modal-btn modal-btn-keep" id="modalKeepBtn">No, Keep Download</button>
            <button class="modal-btn modal-btn-cancel" id="modalCancelBtn">Yes, Cancel</button>
          </div>
        </div>
      `;
      document.body.appendChild(modalOverlay);

      // Close on overlay click
      modalOverlay.addEventListener("click", (e) => {
        if (e.target === modalOverlay) {
          hideModal();
          resolve(false);
        }
      });
    }

    const modalCancelBtn = document.getElementById("modalCancelBtn");
    const modalKeepBtn = document.getElementById("modalKeepBtn");

    // Show modal
    modalOverlay.classList.add("show");

    // Handle button clicks
    const handleCancel = () => {
      hideModal();
      resolve(true);
    };

    const handleKeep = () => {
      hideModal();
      resolve(false);
    };

    const hideModal = () => {
      modalOverlay.classList.remove("show");
      modalCancelBtn.removeEventListener("click", handleCancel);
      modalKeepBtn.removeEventListener("click", handleKeep);
    };

    modalCancelBtn.addEventListener("click", handleCancel);
    modalKeepBtn.addEventListener("click", handleKeep);

    // Focus the "Keep" button by default (safer default)
    modalKeepBtn.focus();
  });
}

// Initialize progress UI to show queued state (0%)
function initializeQueuedState(buttonElement, hasMultiPhase = false) {
  const progressContainer = buttonElement.progressContainer;
  if (!progressContainer) return;

  // Show progress container
  toggleProgressContainer(buttonElement, true);

  if (hasMultiPhase) {
    // Multi-phase progress (for combines)
    const phases = progressContainer.querySelectorAll(".phase-item");
    phases.forEach((phase) => {
      const statusSpan = phase.querySelector(".phase-status");
      if (statusSpan) {
        statusSpan.textContent = "Queued...";
      }
      const progressBar = phase.querySelector(".progress-bar-fill");
      if (progressBar) {
        progressBar.style.width = "0%";
      }
    });
  } else {
    // Single progress bar (for individual downloads)
    const statusSpan = progressContainer.querySelector(".download-status");
    const progressBar = progressContainer.querySelector(".progress-bar-fill");
    if (statusSpan) {
      statusSpan.textContent = "Queued (0%)";
    }
    if (progressBar) {
      progressBar.style.width = "0%";
    }
  }
}

// Set button background based on type and shade
function setButtonBackground(buttonElement, buttonType, shade) {
  const backgrounds = {
    combine: {
      medium: "linear-gradient(135deg, #a569bd, #8e44ad)",
      dark: "linear-gradient(135deg, #8e44ad, #6c3483)",
      darkest: "linear-gradient(135deg, #703080, #512e5f)",
    },
    "video-audio": {
      medium: "linear-gradient(135deg, #2ecc71, #27ae60)",
      dark: "linear-gradient(135deg, #27ae60, #229954)",
      darkest: "linear-gradient(135deg, #1f8b4c, #196f3d)",
    },
    "video-only": {
      medium: "linear-gradient(135deg, #e59866, #d35400)",
      dark: "linear-gradient(135deg, #d35400, #b84900)",
      darkest: "linear-gradient(135deg, #b84900, #a04000)",
    },
    "audio-only": {
      medium: "linear-gradient(135deg, #5dade2, #2980b9)",
      dark: "linear-gradient(135deg, #2980b9, #2471a3)",
      darkest: "linear-gradient(135deg, #2471a3, #1f618d)",
    },
    other: {
      medium: "linear-gradient(135deg, #aeb6bf, #7f8c8d)",
      dark: "linear-gradient(135deg, #7f8c8d, #607070)",
      darkest: "linear-gradient(135deg, #607070, #515a5a)",
    },
  };

  const typeBackgrounds = backgrounds[buttonType] || backgrounds["other"];
  buttonElement.style.background =
    typeBackgrounds[shade] || typeBackgrounds["medium"];
}

// Toggle progress container visibility
function toggleProgressContainer(buttonElement, show) {
  if (buttonElement.progressContainer) {
    buttonElement.progressContainer.style.display = show ? "block" : "none";
  }
}

// Restore button to original state
function restoreButtonState(buttonElement, includeBackground = true) {
  buttonElement.textContent = buttonElement.originalText;
  buttonElement.disabled = false;
  if (includeBackground && buttonElement.originalBackground) {
    buttonElement.style.background = buttonElement.originalBackground;
  }
}

// Attach cancel handler to button during processing
function attachCancelHandler(
  buttonElement,
  taskId,
  originalActionCallback,
  shouldContinuePollingRef
) {
  if (buttonElement.cancelHandlerAttached) return;

  buttonElement.textContent = "Cancel";
  buttonElement.disabled = false;
  buttonElement.cancelHandlerAttached = true;
  buttonElement.currentTaskId = taskId;

  buttonElement.onclick = async function (e) {
    e.preventDefault();
    e.stopPropagation();

    // Show custom confirmation modal
    const confirmed = await showCancelConfirmation();
    if (!confirmed) {
      return;
    }

    try {
      buttonElement.textContent = "Cancelling...";
      buttonElement.disabled = true;

      const response = await fetch(
        `/cancel_task/${buttonElement.currentTaskId}`,
        {
          method: "POST",
        }
      );

      if (response.ok) {
        buttonElement.taskCancelled = true;
        buttonElement.textContent = "Cancelled ❌";
        buttonElement.style.background =
          "linear-gradient(135deg, #95a5a6, #7f8c8d)";
        buttonElement.disabled = false;

        toggleProgressContainer(buttonElement, false);

        if (typeof originalActionCallback === "function") {
          buttonElement.onclick = originalActionCallback;
          buttonElement.cancelHandlerAttached = false;
        }

        // Auto-reset after 3 seconds
        setTimeout(() => {
          if (buttonElement.textContent === "Cancelled ❌") {
            restoreButtonState(buttonElement);
            buttonElement.taskCancelled = false;
            buttonElement.cancelHandlerAttached = false;
          }
        }, 3000);
      } else {
        const error = await response.json();
        alert("Failed to cancel: " + (error.error || "Unknown error"));
        buttonElement.textContent = "Cancel";
        buttonElement.disabled = false;
      }
    } catch (error) {
      console.error("Cancel error:", error);
      alert("Failed to cancel task");
      buttonElement.textContent = "Cancel";
      buttonElement.disabled = false;
    }
  };
}

// --- Task Polling Function ---
function pollTaskStatus(
  statusUrl,
  buttonElement,
  originalButtonText,
  taskId,
  originalActionCallback,
  buttonType
) {
  let pollingInterval = 500; // Start with 500ms polling
  let attempts = 0;
  const maxAttempts = 720; // Max attempts (e.g., 1 hour if polling every 5s)

  // Don't modify button here - cancel handler is already attached

  let shouldContinuePolling = true;
  const pollFunction = async () => {
    // Check if task was cancelled
    if (buttonElement.taskCancelled) {
      return; // Stop polling immediately
    }

    attempts++;
    if (attempts > maxAttempts) {
      shouldContinuePolling = false;
      buttonElement.textContent = "Timeout ⌛";
      buttonElement.style.background =
        "linear-gradient(135deg, #e74c3c, #c0392b)"; // Red for timeout
      buttonElement.disabled = false; // Re-enable
      if (typeof originalActionCallback === "function") {
        buttonElement.onclick = originalActionCallback;
      }
      alert(
        "Task timed out after " +
          (maxAttempts * pollingInterval) / 1000 / 60 +
          " minutes."
      );
      return;
    }

    try {
      const response = await fetch(statusUrl);
      if (!response.ok) {
        // If status endpoint itself fails, stop polling for this task
        console.error("Error fetching task status:", response.status);
        // Potentially update button to show an error, but avoid infinite loops
        // For now, we'll let it timeout or the user can retry manually
        if (response.status === 404) {
          // Task ID might have expired or is wrong
          shouldContinuePolling = false;
          buttonElement.textContent = "Status Error ❓";
          buttonElement.disabled = false;
          if (typeof originalActionCallback === "function") {
            buttonElement.onclick = originalActionCallback;
          }
          alert(
            "Could not find task status. It might have expired or been an issue with the ID."
          );
        }
        return; // Continue polling unless it's a definitive error like 404
      }

      const data = await response.json();

      // Check again if task was cancelled while fetch was in progress
      if (buttonElement.taskCancelled) {
        return; // Don't update UI if cancelled
      }

      let statusText =
        data.status.charAt(0).toUpperCase() + data.status.slice(1);

      if (data.status === "queued") {
        // Queued state - progress UI already shows "Queued", button shows "Cancel"
        // Nothing to do here, just continue polling
      } else if (data.status === "processing") {
        // Update progress display
        if (buttonElement.progressContainer) {
          const progressContainer = buttonElement.progressContainer;
          const phase = data.phase || "";

          // Check if this is a multi-phase combination download or simple individual download
          const hasMultiPhaseStructure = !!progressContainer.querySelector(
            '[data-phase="video"]'
          );

          if (hasMultiPhaseStructure) {
            // Multi-phase progress for combination tasks
            toggleProgressContainer(buttonElement, true);

            const videoPhase = progressContainer.querySelector(
              '[data-phase="video"]'
            );
            const audioPhase = progressContainer.querySelector(
              '[data-phase="audio"]'
            );
            const combiningPhase = progressContainer.querySelector(
              '[data-phase="combining"]'
            );

            if (!videoPhase || !audioPhase || !combiningPhase) {
              console.error("Missing phase elements!");
              buttonElement.textContent = statusText + "... ⏳";
              return;
            }

            const combiningProgress =
              combiningPhase.querySelector(".progress-bar-bg");
            const combiningFill =
              combiningPhase.querySelector(".progress-bar-fill");

            // Get progress bar elements for all phases
            const videoProgress = videoPhase.querySelector(".progress-bar-bg");
            const videoFill = videoPhase.querySelector(".progress-bar-fill");
            const audioProgress = audioPhase.querySelector(".progress-bar-bg");
            const audioFill = audioPhase.querySelector(".progress-bar-fill");

            // Update phases based on current state
            if (phase.includes("downloading_video")) {
              const percent = data.progress_percent || 0;
              videoPhase.querySelector(".phase-icon").textContent = "⏳";
              videoPhase.querySelector(".phase-status").textContent = `${
                data.progress_percent
                  ? data.progress_percent.toFixed(0) + "%"
                  : "In progress..."
              }`;
              videoProgress.style.display = "block";
              videoFill.style.width = percent + "%";
              audioPhase.querySelector(".phase-icon").textContent = "⏳";
              audioPhase.querySelector(".phase-status").textContent =
                "Waiting...";
              audioProgress.style.display = "none";
              combiningPhase.querySelector(".phase-icon").textContent = "⏳";
              combiningPhase.querySelector(".phase-status").textContent =
                "Waiting...";
              combiningProgress.style.display = "none";
            } else if (phase.includes("downloading_audio")) {
              const percent = data.progress_percent || 0;
              videoPhase.querySelector(".phase-icon").textContent = "✓";
              videoPhase.querySelector(".phase-status").textContent =
                "Downloaded";
              videoProgress.style.display = "none";
              audioPhase.querySelector(".phase-icon").textContent = "⏳";
              audioPhase.querySelector(".phase-status").textContent = `${
                data.progress_percent
                  ? data.progress_percent.toFixed(0) + "%"
                  : "In progress..."
              }`;
              audioProgress.style.display = "block";
              audioFill.style.width = percent + "%";
              combiningPhase.querySelector(".phase-icon").textContent = "⏳";
              combiningPhase.querySelector(".phase-status").textContent =
                "Waiting...";
              combiningProgress.style.display = "none";
            } else if (phase === "combining") {
              videoPhase.querySelector(".phase-icon").textContent = "✓";
              videoPhase.querySelector(".phase-status").textContent =
                "Downloaded";
              videoProgress.style.display = "none";
              audioPhase.querySelector(".phase-icon").textContent = "✓";
              audioPhase.querySelector(".phase-status").textContent =
                "Downloaded";
              audioProgress.style.display = "none";
              combiningPhase.querySelector(".phase-icon").textContent = "⏳";
              combiningProgress.style.display = "block";
              combiningFill.style.width = (data.progress_percent || 0) + "%";
              combiningPhase.querySelector(".phase-status").textContent = `${
                data.progress_percent
                  ? data.progress_percent.toFixed(0) + "%"
                  : "0%"
              }`;
            }

            // Attach cancel handler during processing
            attachCancelHandler(buttonElement, taskId, originalActionCallback);
          } else {
            // Simple progress for individual downloads
            toggleProgressContainer(buttonElement, true);

            const statusSpan = progressContainer.querySelector(".download-status");
            const progressFill = progressContainer.querySelector(".progress-bar-fill");
            const labelSpan = progressContainer.querySelector(".download-label");
            const iconSpan = progressContainer.querySelector(".download-icon");
            const percent = data.progress_percent || 0;

            // Check if MP3 conversion phase
            const isMp3Progress = progressContainer.dataset.mp3 === "true";
            const isConverting = data.phase && data.phase.startsWith("converting_mp3");

            if (isMp3Progress && isConverting) {
              // MP3 conversion phase - change label, keep bar at 100%
              if (labelSpan) labelSpan.textContent = "Converting to MP3:";
              if (iconSpan) iconSpan.textContent = "🔄";
              if (statusSpan) statusSpan.textContent = "In progress...";
              if (progressFill) progressFill.style.width = "100%";
            } else {
              // Standard downloading progress
              if (labelSpan) labelSpan.textContent = "Downloading:";
              if (iconSpan) iconSpan.textContent = "🔄";
              if (statusSpan) statusSpan.textContent = `${percent.toFixed(0)}%`;
              if (progressFill) progressFill.style.width = `${percent}%`;
            }

            // Attach cancel handler during processing
            attachCancelHandler(buttonElement, taskId, originalActionCallback);
          }
        } else {
          buttonElement.textContent = statusText + "... ⏳";
        }

        // Speed up polling when actively processing to catch status changes faster
        if (data.status === "processing") {
          pollingInterval = 250; // Poll every 250ms during processing for more responsive updates
        } else {
          pollingInterval = 500; // Normal speed for queued status
        }
        // Set background for queued/processing states
        setButtonBackground(buttonElement, buttonType, "dark");
      } else {
        buttonElement.textContent = statusText + "..."; // For other potential statuses if any
      }

      if (data.status === "completed") {
        shouldContinuePolling = false;

        // Hide progress container
        toggleProgressContainer(buttonElement, false);

        // Update button to indicate download is starting automatically
        buttonElement.textContent = "Downloading... ⏳";
        buttonElement.disabled = true; // Disable while initiating
        setButtonBackground(buttonElement, buttonType, "dark");

        // Automatically trigger the download
        // console.log(`Task ${taskId} completed. Automatically starting download.`);
        window.location.href = `/download_processed/${taskId}`;

        // After a short delay, update button to "Downloaded"
        setTimeout(() => {
          buttonElement.textContent = "Downloaded ✅";
          setButtonBackground(buttonElement, buttonType, "darkest");
        }, 500); // 500ms delay - more responsive
      } else if (data.status === "failed") {
        shouldContinuePolling = false;
        buttonElement.textContent = "Failed ❌";
        buttonElement.disabled = false;
        buttonElement.style.background =
          "linear-gradient(135deg, #e74c3c, #c0392b)"; // Red color

        // Display error message in the progress container
        if (buttonElement.progressContainer) {
          const errorMessage = data.message || "Unknown error";
          buttonElement.progressContainer.innerHTML = `
            <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 12px; margin-top: 8px;">
              <div style="color: #856404; font-weight: 600; margin-bottom: 4px;">❌ Error</div>
              <div style="color: #856404; font-size: 14px;">${errorMessage}</div>
            </div>
          `;
          toggleProgressContainer(buttonElement, true);
        }

        // Restore original action
        if (typeof originalActionCallback === "function") {
          buttonElement.onclick = originalActionCallback;
          buttonElement.cancelHandlerAttached = false;
        }

        // Auto-reset after 5 seconds to allow user to read error message
        setTimeout(() => {
          if (buttonElement.textContent === "Failed ❌") {
            restoreButtonState(buttonElement);
            toggleProgressContainer(buttonElement, false);
            buttonElement.taskCancelled = false;
            buttonElement.cancelHandlerAttached = false;
          }
        }, 5000);
      } else if (data.status === "cancelled") {
        shouldContinuePolling = false;
        buttonElement.textContent = "Cancelled ❌";
        buttonElement.disabled = false;
        buttonElement.style.background =
          "linear-gradient(135deg, #95a5a6, #7f8c8d)"; // Gray color

        // Hide progress container
        toggleProgressContainer(buttonElement, false);

        // Restore original action
        if (typeof originalActionCallback === "function") {
          buttonElement.onclick = originalActionCallback;
          buttonElement.cancelHandlerAttached = false;
        }
      }
      // If 'queued' or 'processing', the loop continues
      // Schedule next poll with dynamic interval
      if (
        shouldContinuePolling &&
        (data.status === "queued" || data.status === "processing")
      ) {
        setTimeout(pollFunction, pollingInterval);
      }
    } catch (error) {
      console.error("Polling error:", error);
      // Continue polling on error if we haven't exceeded max attempts
      if (shouldContinuePolling && attempts < maxAttempts) {
        setTimeout(pollFunction, pollingInterval);
      }
    }
  };

  // Start polling
  pollFunction();
}

// --- End Task Polling Function ---

function addSectionHeader(title, color, sectionType) {
  // Added sectionType
  const header = document.createElement("div");
  header.className = "section-header"; // Apply a common class
  if (sectionType) {
    header.setAttribute("data-section-type", sectionType); // Set data attribute
  }
  // Most inline styles removed, will be handled by CSS.
  // We can keep a fallback or default text color if backgrounds are consistently dark.
  header.style.color = "#ffffff"; // Assuming dark backgrounds from CSS

  header.textContent = title;
  formatList.appendChild(header);
}

function addFormatItem(format, sectionType) {
  const formatItem = document.createElement("div");
  formatItem.className = "format-item";

  let qualityText = "";
  let typeIcon = "";

  if (format.type === "video+audio") {
    qualityText = `${format.quality} (${format.ext.toUpperCase()})`;
    typeIcon = "🎬";
  } else if (format.type === "video-only") {
    qualityText = `${format.quality} (${format.ext.toUpperCase()})`;
    typeIcon = "📹";
  } else if (format.type === "audio-only") {
    qualityText = `${format.quality} (${
      format.ext ? format.ext.toUpperCase() : "N/A"
    })`;
    typeIcon = "🎵";
  } else {
    // 'other' type
    qualityText = `${format.quality || "Unknown"} (${
      format.ext ? format.ext.toUpperCase() : "N/A"
    })`;
    typeIcon = "❓";
  }

  let codecInfo;
  if (format.type.includes("video")) {
    const videoCodec =
      format.vcodec && format.vcodec !== "none" ? format.vcodec : "Unknown";
    const audioCodecInVideo =
      format.acodec && format.acodec !== "none" ? format.acodec : "N/A";
    codecInfo = `${format.width || "?"}x${
      format.height || "?"
    } | Video: ${videoCodec}`;
    if (format.type === "video+audio") {
      codecInfo += ` | Audio: ${audioCodecInVideo}`;
    }
  } else if (format.type === "audio-only") {
    const audioCodec =
      format.acodec && format.acodec !== "none" ? format.acodec : "Unknown";
    codecInfo = `Audio Codec: ${audioCodec}`;
  } else {
    // 'other' type
    codecInfo = "Format details not available";
  }

  const detailsDiv = document.createElement("div");
  detailsDiv.className = "format-details";
  const sizeDisplay =
    format.filesize && format.filesize !== "N/A"
      ? ` | Size: ${format.filesize}`
      : "";
  detailsDiv.innerHTML = `
      <div class="format-type">${typeIcon} ${qualityText}</div>
      <div class="format-specs">${codecInfo}${sizeDisplay}</div>
  `;

  const actionsDiv = document.createElement("div");
  actionsDiv.style.display = "flex";
  actionsDiv.style.gap = "8px";

  const downloadButton = document.createElement("button");
  downloadButton.className = "download-btn";
  downloadButton.textContent = "⬇ Download";
  // Set initial background based on sectionType
  switch (sectionType) {
    case "video-audio":
      downloadButton.style.background =
        "linear-gradient(135deg, #2ecc71, #27ae60)"; // Medium Green
      break;
    case "video-only":
      downloadButton.style.background =
        "linear-gradient(135deg, #e59866, #d35400)"; // Medium Orange
      break;
    case "audio-only":
      downloadButton.style.background =
        "linear-gradient(135deg, #5dade2, #2980b9)"; // Medium Blue
      break;
    case "other":
    default:
      downloadButton.style.background =
        "linear-gradient(135deg, #aeb6bf, #7f8c8d)"; // Medium Grey (fallback)
      break;
  }

  // Store original text and background ONCE when button is created
  downloadButton.originalText = downloadButton.textContent;
  downloadButton.originalBackground = downloadButton.style.background;

  // Use onclick instead of addEventListener for consistent handler replacement
  downloadButton.onclick = () =>
    queueIndividualDownload(format, downloadButton, sectionType);

  actionsDiv.appendChild(downloadButton);

  // Wrap details and actions in a content container
  const contentWrapper = document.createElement("div");
  contentWrapper.className = "format-item-content";
  contentWrapper.appendChild(detailsDiv);
  contentWrapper.appendChild(actionsDiv);

  // Add progress bar container for individual downloads
  const progressContainer = document.createElement("div");
  progressContainer.className = "progress-container";
  progressContainer.style.display = "none";

  // Mark MP3 conversions for dynamic label change during conversion phase
  const isMp3Conversion = format.format_id && format.format_id.startsWith("bestaudio_mp3");
  if (isMp3Conversion) {
    progressContainer.dataset.mp3 = "true";
  }
  progressContainer.innerHTML = `
    <div style="display: flex; align-items: center; gap: 6px; font-size: 13px; padding: 2px 0;">
      <span class="download-icon" style="font-size: 15px;">⏳</span>
      <span class="download-label" style="font-weight: 600; color: #2c3e50;">Downloading:</span>
      <span class="download-status" style="color: #7f8c8d; font-weight: 500;">0%</span>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" style="width: 0%"></div>
    </div>
  `;

  formatItem.appendChild(contentWrapper);
  formatItem.appendChild(progressContainer);
  formatList.appendChild(formatItem);

  // Store reference to progress container on button for easy access
  downloadButton.progressContainer = progressContainer;
}

// Queues an individual download using the backend task queue system
async function queueIndividualDownload(format, buttonElement, sectionType) {
  // Clear any previous cancellation flag
  buttonElement.taskCancelled = false;
  buttonElement.cancelHandlerAttached = false;

  // console.log(`Queueing individual download for format ID: ${format.format_id}`);
  // Show queued state immediately
  initializeQueuedState(buttonElement, false); // single progress bar for all individual downloads

  try {
    const currentUrl = urlInput.value.trim();
    const videoTitle = window.currentVideoTitle || "video"; // Use stored title or a default

    if (!currentUrl) {
      alert("Please ensure the YouTube URL is still in the input field.");
      buttonElement.textContent = originalButtonText;
      buttonElement.disabled = false;
      return;
    }
    if (!format || !format.format_id) {
      alert("Format details are missing. Cannot queue download.");
      buttonElement.textContent = originalButtonText;
      buttonElement.disabled = false;
      return;
    }

    const response = await fetch("/queue_individual_download", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: currentUrl,
        format_id: format.format_id,
        selected_format_details: format,
        video_title: videoTitle,
      }),
    });

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ error: "Failed to queue download. Server error." }));
      throw new Error(
        errorData.error || `Server responded with status ${response.status}`
      );
    }

    const data = await response.json();

    // Attach cancel handler immediately (works for both queued and processing)
    attachCancelHandler(buttonElement, data.task_id, () =>
      queueIndividualDownload(format, buttonElement, sectionType)
    );

    // Start polling for task status
    pollTaskStatus(
      data.status_url,
      buttonElement,
      buttonElement.originalText,
      data.task_id,
      () => queueIndividualDownload(format, buttonElement, sectionType), // Pass sectionType for retry
      sectionType // Pass current sectionType as buttonType
    );
  } catch (error) {
    console.error("Error queueing individual download:", error);
    alert(`Failed to queue download: ${error.message}`);
    restoreButtonState(buttonElement);
    toggleProgressContainer(buttonElement, false);
  }
}

// Fetches video information and available formats from the server's /extract endpoint.
async function extractVideoInfo() {
  const url = urlInput.value.trim();
  if (!url) {
    alert("Please enter a YouTube URL.");
    return;
  }

  if (!isValidYouTubeUrl(url)) {
    alert(
      "Invalid YouTube URL. Please use a valid format (e.g., youtube.com/watch?v=... or youtu.be/...)"
    );
    return;
  }

  showLoading(); // Disable button during processing

  try {
    const response = await fetch("/extract", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: url }),
    });

    if (response.ok) {
      const data = await response.json();
      displayResults(data);
    } else {
      const error = await response.json();
      alert("Extraction failed: " + (error.error || "Unknown error"));
    }
  } catch (error) {
    alert("Extraction error: " + error.message);
  } finally {
    hideLoading(); // Re-enable button and hide loading indicator
  }
}

// New function to reset the page state:
function resetPage() {
  urlInput.value = "";
  results.style.display = "none";
  videoInfo.innerHTML =
    '<img id="videoThumbnail" src="" alt="Video Thumbnail">'; // Reset video info, keeping the img tag for future use
  document.getElementById("videoThumbnail").style.display = "none"; // Ensure thumbnail is hidden
  formatList.innerHTML = "";
  if (clearInputIcon) clearInputIcon.style.display = "none"; // Hide clear icon
  urlInput.focus();
}

// Event listeners
extractBtn.addEventListener("click", extractVideoInfo);

urlInput.addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    extractVideoInfo();
  }
});

urlInput.addEventListener("input", function () {
  // Show/hide clear icon based on input value if results are visible
  if (results.style.display === "block") {
    if (urlInput.value.trim() !== "") {
      if (clearInputIcon) clearInputIcon.style.display = "block";
    } else {
      if (clearInputIcon) clearInputIcon.style.display = "none";
    }
    // Optionally, also hide results if input is cleared *after* extraction
    // results.style.display = 'none'; // This would hide results immediately on clearing input
  } else {
    // If results are not visible, the clear icon should also not be visible
    if (clearInputIcon) clearInputIcon.style.display = "none";
  }
});

if (clearInputIcon) {
  clearInputIcon.addEventListener("click", resetPage);
}

// Easter Egg: Double-click on the main title to populate the Rick Roll URL
const pageTitle = document.querySelector(".header h1");
const rickRollUrl = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";

if (pageTitle) {
  pageTitle.style.userSelect = "none"; // Prevent text selection
  pageTitle.addEventListener("dblclick", function (e) {
    e.preventDefault(); // Prevent default text selection behavior
    urlInput.value = rickRollUrl;
    urlInput.focus(); // Move focus to the input field
    // Optional: A little wink to the console for those who find it
    console.log("Never gonna give you up... Never gonna let you down...");
  });
}
