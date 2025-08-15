const urlInput = document.getElementById("urlInput");
const extractBtn = document.getElementById("extractBtn");
const loading = document.getElementById("loading");
const results = document.getElementById("results");
const videoInfo = document.getElementById("videoInfo");
const formatList = document.getElementById("formatList");
const clearInputIcon = document.getElementById('clearInputIcon');

function isValidYouTubeUrl(url) {
  const regex =
    /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[a-zA-Z0-9_-]{11}/;
  return regex.test(url);
}

function extractVideoId(url) {
  const match = url.match(
    /(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/
  );
  return match ? match[1] : null;
}

function showLoading() {
  loading.style.display = "block";
  results.style.display = "none";
  extractBtn.disabled = true;
  extractBtn.textContent = "Processing...";
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
  window.currentFormats = data.formats;

  if (urlInput.value.trim() !== '' && clearInputIcon) {
    clearInputIcon.style.display = 'block';
  }

  // --- START: Thumbnail Handling ---
  const thumbnailImg = document.getElementById('videoThumbnail');
  if (data.thumbnail_url) {
    thumbnailImg.src = data.thumbnail_url;
    thumbnailImg.style.display = 'block'; 
  } else {
    thumbnailImg.style.display = 'none';
    thumbnailImg.src = ''; // Clear src if no thumbnail
  }
  // --- END: Thumbnail Handling ---

  // Clear previous text info (but not the thumbnail image)
  let textInfoDiv = videoInfo.querySelector('.video-text-details');
  if (textInfoDiv) {
    textInfoDiv.remove();
  }
  
  textInfoDiv = document.createElement('div');
  textInfoDiv.className = 'video-text-details'; // Add a class for potential styling
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
  const videoOnlyFormats = data.formats.filter(
    (f) => f.type === "video-only"
  );
  const audioOnlyFormats = data.formats.filter(
    (f) => f.type === "audio-only"
  );
  const otherFormats = data.formats.filter((f) => f.type === "other");

  // Add Combined High Quality section FIRST (most useful)
  if (videoOnlyFormats.length > 0 && audioOnlyFormats.length > 0) {
    addCombinedSection(videoOnlyFormats, audioOnlyFormats);
  }

  // Add Video + Audio section
  if (videoAudioFormats.length > 0) {
    addSectionHeader("🎬 Video + Audio (Ready to Use)", "#27ae60", "video-audio");
    videoAudioFormats.forEach((format) => addFormatItem(format, "video-audio"));
  }

  // Add Video Only section
  if (videoOnlyFormats.length > 0) {
    addSectionHeader("📹 Video Only (No Audio)", "#e67e22", "video-only");
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
  addSectionHeader("⚡ High Quality Combined (Best Choice)", "#8e44ad", "high-quality");

  // Get best audio format for combining
  // Assumes audioFormats is already sorted by quality (best first) by the server.
  const bestAudio = audioFormats[0];

  // Create combination options using the video-only formats provided by the server.
  // (These are typically pre-filtered for reasonable quality, e.g., >=480p, on the server-side).
  const topVideoFormats = videoFormats; // Use all video formats provided by the server (already filtered >= 480p)

  topVideoFormats.forEach((videoFormat, index) => {
    const combinedItem = document.createElement("div");
    combinedItem.className = "format-item";
    combinedItem.style.background =
      "linear-gradient(135deg, #f8f9fa, #e9ecef)";
    combinedItem.style.border = "2px solid #8e44ad22";

    // Use the actual video format quality, not hardcoded
    const videoQualityDisplay = `${videoFormat.quality || videoFormat.height + "p" || "Unknown Video"}`;
    const codecInfo = `Video: ${videoFormat.width || "?"}x${videoFormat.height || "?"} + Best Available Audio | Auto-combined`;

    const qualityText = `${
      videoFormat.quality || videoFormat.height + "p" || "Unknown"
    } + Best Audio`;
    combinedItem.innerHTML = `
    <div class="format-details">
        <div class="format-type">⚡ ${videoQualityDisplay} + Best Audio (MP4) [Format ${videoFormat.format_id}]</div>
        <div class="format-specs">${codecInfo}</div>
    </div>
    <div style="display: flex; gap: 8px;">
        <button class="download-btn" style="background: linear-gradient(135deg, #a569bd, #8e44ad);">
            ⚡ Combine & Download
        </button>
    </div>
`;

    formatList.appendChild(combinedItem);

    // Add event listener to the button after it's created and appended
    const button = combinedItem.querySelector('.download-btn');
    button.addEventListener('click', function() {
      combineVideoAudio(videoFormat, bestAudio, this);
    });
  });
}

async function combineVideoAudio(
  videoFormat,    // Full video format object
  audioFormat,    // Full audio format object
  buttonElement
  // videoTitle can be accessed via window.currentVideoTitle
) {
  // This function calls the server's /combine endpoint to get a merged video and audio file.
  try {
    const currentUrl = urlInput.value.trim();

    const button =
      buttonElement ||
      (typeof event !== "undefined" ? event.target : null);
    if (!button) {
      console.error("Button element not found");
      return;
    }

    const originalText = button.textContent;
    button.textContent = "⏳ Processing...";
    button.disabled = true;
    button.style.background = "linear-gradient(135deg, #8e44ad, #6c3483)"; // Slightly Darker Purple

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
        // videoResolution and videoVcodec are now part of video_format_details
        // audioAcodec and extensions are now part of their respective details objects
      }),
    });

    if (response.ok) {
      // Attempt to parse the filename from the 'Content-Disposition' header.
      // This header can have different formats, so we try to handle common ones.
      let filename = "combined_video.mp4";

      try {
        const contentDisposition = response.headers.get(
          "Content-Disposition"
        );
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
        console.error(
          "Error parsing filename from headers:",
          headerError
        );
        // Keep default filename
      }

      // The /combine endpoint returns JSON with a task_id for polling, not the file directly.
      const result = await response.json();
      button.textContent = "Queued... ⏳"; // Update button text for consistency with pollTaskStatus
      // No longer disable, or make it a cancel button (future enhancement)
      // Start polling for task status
      pollTaskStatus(result.status_url, button, originalText, result.task_id, 
            () => combineVideoAudio(videoFormat, audioFormat, button), // Pass the full objects for retry
            'combine' // Add buttonType
        );
    } else {
      const error = await response.json();
      alert("Combination failed: " + (error.error || "Unknown error"));
    }

    // Restore button
    // Button state is now managed by pollTaskStatus or if initial queuing fails
    if (!response.ok) { // Only restore if the initial queueing failed
       button.textContent = originalText;
       button.disabled = false;
    }
  } catch (error) {
    console.error("Combination error:", error);
    alert("Combination failed: " + error.message);
    // Restore button
    const button =
      buttonElement ||
      (typeof event !== "undefined" ? event.target : null);
    if (button) {
      // Restore button text if an unexpected error occurs during fetch setup
      button.textContent = originalText || "⚡ Combine & Download (Error)";
      button.disabled = false;
    }
  }
}

// --- Task Polling Function ---
function pollTaskStatus(statusUrl, buttonElement, originalButtonText, taskId, originalActionCallback, buttonType) {
  const pollingInterval = 1000; // Poll every 1 second
  let attempts = 0;
  const maxAttempts = 720; // Max attempts (e.g., 1 hour if polling every 5s)

  buttonElement.textContent = "Queued... ⏳";
  buttonElement.disabled = true; // Keep disabled while polling

  const intervalId = setInterval(async () => {
    attempts++;
    if (attempts > maxAttempts) {
      clearInterval(intervalId);
      buttonElement.textContent = "Timeout ⌛";
      buttonElement.style.background = "linear-gradient(135deg, #e74c3c, #c0392b)"; // Red for timeout
      buttonElement.disabled = false; // Re-enable
      if (typeof originalActionCallback === 'function') { buttonElement.onclick = originalActionCallback; }
      alert("Task timed out after " + (maxAttempts * pollingInterval / 1000 / 60) + " minutes.");
      return;
    }

    try {
      const response = await fetch(statusUrl);
      if (!response.ok) {
        // If status endpoint itself fails, stop polling for this task
        console.error("Error fetching task status:", response.status);
        // Potentially update button to show an error, but avoid infinite loops
        // For now, we'll let it timeout or the user can retry manually
        if (response.status === 404) { // Task ID might have expired or is wrong
          clearInterval(intervalId);
          buttonElement.textContent = "Status Error ❓";
          buttonElement.disabled = false;
          if (typeof originalActionCallback === 'function') { buttonElement.onclick = originalActionCallback; }
          alert("Could not find task status. It might have expired or been an issue with the ID.");
        }
        return; // Continue polling unless it's a definitive error like 404
      }

      const data = await response.json();
      let statusText = data.status.charAt(0).toUpperCase() + data.status.slice(1);
      if (data.status === "queued" || data.status === "processing") {
        buttonElement.textContent = statusText + "... ⏳";
        // Ensure correct background for these polling states
        // Ensure correct background for these polling states (Slightly Darker shades)
        if (buttonType === 'combine') {
          buttonElement.style.background = "linear-gradient(135deg, #8e44ad, #6c3483)"; // Slightly Darker Purple
        } else if (buttonType === 'video-audio') {
          buttonElement.style.background = "linear-gradient(135deg, #27ae60, #229954)"; // Slightly Darker Green
        } else if (buttonType === 'video-only') {
          buttonElement.style.background = "linear-gradient(135deg, #d35400, #b84900)"; // Slightly Darker Orange
        } else if (buttonType === 'audio-only') {
          buttonElement.style.background = "linear-gradient(135deg, #2980b9, #2471a3)"; // Slightly Darker Blue
        } else { // 'other' or fallback
          buttonElement.style.background = "linear-gradient(135deg, #7f8c8d, #607070)"; // Slightly Darker Grey
        }
      } else {
        buttonElement.textContent = statusText + "..."; // For other potential statuses if any
      }

      if (data.status === "completed") {
        clearInterval(intervalId);
        
        // Update button to indicate download is starting automatically
        buttonElement.textContent = "Downloading... ⏳";
        buttonElement.disabled = true; // Disable while initiating
        // "Downloading..." state (Slightly Darker shades)
        if (buttonType === 'combine') {
          buttonElement.style.background = "linear-gradient(135deg, #8e44ad, #6c3483)"; 
        } else if (buttonType === 'video-audio') {
          buttonElement.style.background = "linear-gradient(135deg, #27ae60, #229954)";
        } else if (buttonType === 'video-only') {
          buttonElement.style.background = "linear-gradient(135deg, #d35400, #b84900)";
        } else if (buttonType === 'audio-only') {
          buttonElement.style.background = "linear-gradient(135deg, #2980b9, #2471a3)";
        } else { // 'other' or fallback
          buttonElement.style.background = "linear-gradient(135deg, #7f8c8d, #607070)";
        }

        // Automatically trigger the download
        // console.log(`Task ${taskId} completed. Automatically starting download.`);
        window.location.href = `/download_processed/${taskId}`;

        // After a short delay, update button to "Downloaded"
        setTimeout(() => {
          buttonElement.textContent = "Downloaded ✅";
          // Consider keeping it disabled or re-enabling if appropriate
          // "Downloaded" state (Darkest shades)
          if (buttonType === 'combine') {
            buttonElement.style.background = "linear-gradient(135deg, #703080, #512e5f)"; 
          } else if (buttonType === 'video-audio') {
            buttonElement.style.background = "linear-gradient(135deg, #1f8b4c, #196f3d)";
          } else if (buttonType === 'video-only') {
            buttonElement.style.background = "linear-gradient(135deg, #b84900, #a04000)";
          } else if (buttonType === 'audio-only') {
            buttonElement.style.background = "linear-gradient(135deg, #2471a3, #1f618d)";
          } else { // 'other' or fallback
            buttonElement.style.background = "linear-gradient(135deg, #607070, #515a5a)";
          }
        }, 3000); // 3 seconds delay

        buttonElement.classList.remove('queueing-active'); // Example if such a class exists
        buttonElement.classList.add('download-initiated'); // Example for new state
      } else if (data.status === "failed") {
        clearInterval(intervalId);
        buttonElement.textContent = "Failed ❌";
        buttonElement.disabled = false;
        buttonElement.style.background = "linear-gradient(135deg, #e74c3c, #c0392b)"; // Red color
        alert("Combination task failed: " + (data.message || "Unknown error"));
        // Restore original action by re-assigning original click handler if needed
        // For now, user has to re-initiate the process by clicking "Extract Info" again or refreshing.
        // Or, restore the original action:
        if (typeof originalActionCallback === 'function') { buttonElement.onclick = originalActionCallback; }
      }
      // If 'queued' or 'processing', the loop continues
    } catch (error) {
      console.error("Polling error:", error);
      // Potentially stop polling if there are too many network errors
    }
  }, pollingInterval);
}

// --- End Task Polling Function ---

function addSectionHeader(title, color, sectionType) { // Added sectionType
  const header = document.createElement("div");
  header.className = 'section-header'; // Apply a common class
  if (sectionType) {
    header.setAttribute('data-section-type', sectionType); // Set data attribute
  }
  // Most inline styles removed, will be handled by CSS.
  // We can keep a fallback or default text color if backgrounds are consistently dark.
  header.style.color = '#ffffff'; // Assuming dark backgrounds from CSS

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
    qualityText = `${format.quality} (${format.ext ? format.ext.toUpperCase() : 'N/A'})`; 
    typeIcon = "🎵";
  } else { // 'other' type
    qualityText = `${format.quality || 'Unknown'} (${format.ext ? format.ext.toUpperCase() : 'N/A'})`;
    typeIcon = "❓";
  }

  let codecInfo;
  if (format.type.includes("video")) {
    const videoCodec = (format.vcodec && format.vcodec !== 'none') ? format.vcodec : 'Unknown';
    const audioCodecInVideo = (format.acodec && format.acodec !== 'none') ? format.acodec : 'N/A';
    codecInfo = `${format.width || "?"}x${format.height || "?"} | Video: ${videoCodec}`;
    if (format.type === "video+audio") {
        codecInfo += ` | Audio: ${audioCodecInVideo}`;
    }
  } else if (format.type === "audio-only") {
    const audioCodec = (format.acodec && format.acodec !== 'none') ? format.acodec : 'Unknown';
    codecInfo = `Audio Codec: ${audioCodec}`; 
  } else { // 'other' type
    codecInfo = "Format details not available";
  }

  const detailsDiv = document.createElement('div');
  detailsDiv.className = 'format-details';
  const sizeDisplay = (format.filesize && format.filesize !== 'N/A') ? ` | Size: ${format.filesize}` : '';
  detailsDiv.innerHTML = `
      <div class="format-type">${typeIcon} ${qualityText}</div>
      <div class="format-specs">${codecInfo}${sizeDisplay}</div>
  `;

  const actionsDiv = document.createElement('div');
  actionsDiv.style.display = 'flex';
  actionsDiv.style.gap = '8px';

  const downloadButton = document.createElement('button');
  downloadButton.className = 'download-btn'; 
  downloadButton.textContent = '⬇ Download';
  // Set initial background based on sectionType
  switch (sectionType) {
    case 'video-audio':
      downloadButton.style.background = 'linear-gradient(135deg, #2ecc71, #27ae60)'; // Medium Green
      break;
    case 'video-only':
      downloadButton.style.background = 'linear-gradient(135deg, #e59866, #d35400)'; // Medium Orange
      break;
    case 'audio-only':
      downloadButton.style.background = 'linear-gradient(135deg, #5dade2, #2980b9)'; // Medium Blue
      break;
    case 'other':
    default:
      downloadButton.style.background = 'linear-gradient(135deg, #aeb6bf, #7f8c8d)'; // Medium Grey (fallback)
      break;
  }
  // Attach event listener to call queueIndividualDownload, passing the full format object, the button itself, and sectionType
  downloadButton.addEventListener('click', () => queueIndividualDownload(format, downloadButton, sectionType));
  
  actionsDiv.appendChild(downloadButton);

  formatItem.appendChild(detailsDiv);
  formatItem.appendChild(actionsDiv);
  formatList.appendChild(formatItem);
}

// Queues an individual download using the backend task queue system
async function queueIndividualDownload(format, buttonElement, sectionType) {
  // console.log(`Queueing individual download for format ID: ${format.format_id}`);
  const originalButtonText = buttonElement.textContent;
  buttonElement.textContent = 'Queuing... ⏳';
  buttonElement.disabled = true;
  // Set background based on sectionType
  switch (sectionType) {
    case 'video-audio':
      buttonElement.style.background = 'linear-gradient(135deg, #27ae60, #229954)'; // Slightly Darker Green
      break;
    case 'video-only':
      buttonElement.style.background = 'linear-gradient(135deg, #d35400, #b84900)'; // Slightly Darker Orange
      break;
    case 'audio-only':
      buttonElement.style.background = 'linear-gradient(135deg, #2980b9, #2471a3)'; // Slightly Darker Blue
      break;
    case 'other':
    default:
      buttonElement.style.background = 'linear-gradient(135deg, #7f8c8d, #607070)'; // Slightly Darker Grey
      break;
  }

  try {
    const currentUrl = urlInput.value.trim();
    const videoTitle = window.currentVideoTitle || 'video'; // Use stored title or a default

    if (!currentUrl) {
      alert('Please ensure the YouTube URL is still in the input field.');
      buttonElement.textContent = originalButtonText;
      buttonElement.disabled = false;
      return;
    }
    if (!format || !format.format_id) {
        alert('Format details are missing. Cannot queue download.');
        buttonElement.textContent = originalButtonText;
        buttonElement.disabled = false;
        return;
    }

    

    const response = await fetch('/queue_individual_download', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: currentUrl,
        format_id: format.format_id,
        selected_format_details: format, 
        video_title: videoTitle
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Failed to queue download. Server error.' }));
      throw new Error(errorData.error || `Server responded with status ${response.status}`);
    }

    const data = await response.json();
    
    buttonElement.textContent = 'Queued'; 
    pollTaskStatus(data.status_url, buttonElement, originalButtonText, data.task_id, 
            () => queueIndividualDownload(format, buttonElement, sectionType), // Pass sectionType for retry
            sectionType // Pass current sectionType as buttonType

        );

  } catch (error) {
    console.error('Error queueing individual download:', error);
    alert(`Failed to queue download: ${error.message}`);
    buttonElement.textContent = originalButtonText;
    buttonElement.disabled = false;
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
  urlInput.value = '';
  results.style.display = 'none';
  videoInfo.innerHTML = '<img id="videoThumbnail" src="" alt="Video Thumbnail">'; // Reset video info, keeping the img tag for future use
  document.getElementById('videoThumbnail').style.display = 'none'; // Ensure thumbnail is hidden
  formatList.innerHTML = '';
  if (clearInputIcon) clearInputIcon.style.display = 'none'; // Hide clear icon
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
  if (results.style.display === 'block') {
    if (urlInput.value.trim() !== '') {
      if (clearInputIcon) clearInputIcon.style.display = 'block';
    } else {
      if (clearInputIcon) clearInputIcon.style.display = 'none';
    }
    // Optionally, also hide results if input is cleared *after* extraction
    // results.style.display = 'none'; // This would hide results immediately on clearing input
  } else {
    // If results are not visible, the clear icon should also not be visible
    if (clearInputIcon) clearInputIcon.style.display = 'none';
  }
});

if (clearInputIcon) {
  clearInputIcon.addEventListener('click', resetPage);
}

// Easter Egg: Double-click on the main title to populate the Rick Roll URL
const pageTitle = document.querySelector('.header h1');
const rickRollUrl = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';

if (pageTitle) {
  pageTitle.addEventListener('dblclick', function() {
    urlInput.value = rickRollUrl;
    urlInput.focus(); // Move focus to the input field
    // Optional: A little wink to the console for those who find it
    console.log('Never gonna give you up... Never gonna let you down...');
  });
}
