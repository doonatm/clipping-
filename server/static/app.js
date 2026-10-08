// AutoShorts Web Platform Client

let state = {
  currentProjectId: null,
  projects: [],
  detail: null,
  environment: null,
  selectedFile: null
};

// Utilities
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return "00:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}"></i>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  lucide.createIcons();
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// API Calls
async function fetchEnvironment() {
  try {
    const res = await fetch("/api/environment");
    state.environment = await res.json();
    updateDiagnosticsUI();
  } catch (err) {
    console.error("Failed to load environment", err);
  }
}

async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    state.projects = await res.json();
    renderProjectList();
  } catch (err) {
    console.error("Failed to load projects", err);
  }
}

async function selectProject(id) {
  state.currentProjectId = id;
  renderProjectList();

  try {
    const res = await fetch(`/api/projects/${id}`);
    if (!res.ok) throw new Error("Could not load project details");
    state.detail = await res.json();
    renderWorkspace();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Render UI Components
function renderProjectList() {
  const listEl = document.getElementById("projectList");
  const countBadge = document.getElementById("projectCountBadge");
  countBadge.textContent = state.projects.length;

  if (state.projects.length === 0) {
    listEl.innerHTML = `
      <div class="project-list-empty">
        <i data-lucide="film"></i>
        <p>No projects yet.<br>Click <strong>Upload Media</strong> or <strong>Instant Demo</strong> to begin!</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  listEl.innerHTML = "";
  state.projects.forEach(p => {
    const item = document.createElement("div");
    item.className = `project-item ${p.id === state.currentProjectId ? 'active' : ''}`;
    item.onclick = () => selectProject(p.id);

    const statusClass = `status-${p.status}`;
    const durationText = p.source_duration ? formatTime(p.source_duration) : '--:--';

    item.innerHTML = `
      <div class="project-item-top">
        <span class="project-item-name" title="${p.name || 'Untitled'}">${p.name || 'Untitled'}</span>
        <span class="status-pill ${statusClass}">${p.status}</span>
      </div>
      <div class="project-item-bottom">
        <span>${new Date(p.created_at).toLocaleDateString()}</span>
        <span class="meta-pill"><i data-lucide="clock" size="12"></i> ${durationText}</span>
      </div>
    `;
    listEl.appendChild(item);
  });
  lucide.createIcons();
}

function renderWorkspace() {
  const emptyView = document.getElementById("emptyState");
  const workspaceView = document.getElementById("projectWorkspace");

  if (!state.detail) {
    emptyView.style.display = "flex";
    workspaceView.style.display = "none";
    return;
  }

  emptyView.style.display = "none";
  workspaceView.style.display = "flex";

  const { project, transcript, candidates, clips } = state.detail;

  // Header Details
  document.getElementById("currentProjectTitle").textContent = project.name || "Untitled Project";
  const statusBadge = document.getElementById("currentProjectStatusBadge");
  statusBadge.className = `status-pill status-${project.status}`;
  statusBadge.textContent = project.status;
  document.getElementById("currentProjectDuration").innerHTML = `
    <i data-lucide="clock"></i> ${formatTime(project.sourceDuration)}
  `;

  // Source Video Player
  const videoPlayer = document.getElementById("sourceVideoPlayer");
  const streamUrl = `/api/media/stream/${project.id}`;
  if (videoPlayer.getAttribute("data-loaded-id") !== project.id) {
    videoPlayer.src = streamUrl;
    videoPlayer.setAttribute("data-loaded-id", project.id);
  }

  // Transcript Rendering
  const transcriptBody = document.getElementById("transcriptContent");
  const wordCountBadge = document.getElementById("transcriptWordCount");

  if (transcript && transcript.rawJson) {
    try {
      const data = JSON.parse(transcript.rawJson);
      wordCountBadge.textContent = `${data.words ? data.words.length : 0} words`;

      if (data.segments && data.segments.length > 0) {
        transcriptBody.innerHTML = data.segments.map(seg => `
          <div class="transcript-segment" onclick="seekVideo(${seg.start})">
            <div class="segment-meta">
              <span>${seg.speaker || 'Speaker'}</span>
              <span>${formatTime(seg.start)} - ${formatTime(seg.end)}</span>
            </div>
            <p class="segment-text">${seg.text}</p>
          </div>
        `).join("");
      } else {
        transcriptBody.innerHTML = `<div class="empty-transcript"><p>Empty transcript.</p></div>`;
      }
    } catch (e) {
      transcriptBody.innerHTML = `<div class="empty-transcript"><p>Could not parse transcript.</p></div>`;
    }
  } else {
    wordCountBadge.textContent = "0 words";
    transcriptBody.innerHTML = `
      <div class="empty-transcript">
        <p>No transcript generated yet.<br>Click <strong>Transcribe</strong> above to start speech recognition.</p>
      </div>
    `;
  }

  // Candidates & Clips Rendering
  const candidatesList = document.getElementById("candidatesList");
  const countBadge = document.getElementById("candidateCountBadge");
  countBadge.textContent = candidates.length;

  const clipMap = new Map();
  clips.forEach(c => clipMap.set(c.candidateId, c));

  if (candidates.length === 0) {
    candidatesList.innerHTML = `
      <div class="empty-candidates">
        <div class="empty-icon-glow" style="width: 54px; height: 54px;">
          <i data-lucide="sparkles"></i>
        </div>
        <h4 style="font-size: 1.1rem; font-weight: 700;">Ready to Extract Viral Clips</h4>
        <p style="max-width: 360px; line-height: 1.5; color: var(--text-secondary);">Click below to analyze the speech, identify high-impact hooks, and rank viral shorts automatically.</p>
        <button class="btn btn-primary" onclick="handleDetectMoments()" style="margin-top: 8px;">
          <i data-lucide="wand-2"></i>
          <span>Extract Viral Clips Now</span>
        </button>
      </div>
    `;
  } else {
    candidatesList.innerHTML = candidates.map(c => {
      const clip = clipMap.get(c.id);
      const isDone = clip && clip.status === "done" && clip.outputPath;
      const isRendering = clip && clip.status === "rendering";
      const matchScore = Math.round((c.score || 0.85) * 100);

      return `
        <div class="candidate-card ${c.selected ? 'selected' : ''}" id="card-${c.id}">
          <div class="candidate-card-header">
            <span class="badge-rank">#${c.rank}</span>
            <span class="badge-match"><i data-lucide="flame" size="12"></i> ${matchScore}% Viral Match</span>
          </div>

          <div class="candidate-card-middle">
            <div class="portrait-thumbnail ${isDone ? 'rendered' : ''}" onclick="${isDone ? `playPhoneClip('${c.id}', ${c.rank}, ${matchScore}, '${escapeQuotes(c.hook)}', '${escapeQuotes(c.rationale)}')` : `renderSingleClip('${c.id}')`}">
              ${isDone ? `
                <i data-lucide="play" size="24"></i>
                <span>9:16</span>
                <div class="play-overlay"><i data-lucide="play-circle" size="32"></i></div>
              ` : `
                <i data-lucide="${isRendering ? 'loader-2' : 'scissors'}" class="${isRendering ? 'spin' : ''}" size="20"></i>
                <span>${isRendering ? '...' : '9:16'}</span>
              `}
            </div>

            <div class="candidate-content">
              <h4 class="candidate-hook" title="${c.hook}">"${c.hook}"</h4>
              <p class="candidate-rationale" title="${c.rationale}">${c.rationale}</p>
              <div class="candidate-timing">
                <i data-lucide="clock" size="12"></i>
                <span>${formatTime(c.startSec)} - ${formatTime(c.endSec)} (${Math.round(c.endSec - c.startSec)}s)</span>
              </div>
            </div>
          </div>

          <div class="candidate-card-footer">
            <div class="action-buttons-group">
              ${isDone ? `
                <button class="btn btn-primary btn-sm" onclick="playPhoneClip('${c.id}', ${c.rank}, ${matchScore}, '${escapeQuotes(c.hook)}', '${escapeQuotes(c.rationale)}')">
                  <i data-lucide="play"></i>
                  <span>Play Clip</span>
                </button>
                <a href="/api/media/clips/${c.id}/download" download class="btn btn-secondary btn-sm" title="Download 9:16 MP4">
                  <i data-lucide="download"></i>
                  <span>MP4</span>
                </a>
                <a href="/api/media/clips/${c.id}/subtitles" download class="btn btn-secondary btn-sm" title="Download Subtitles (.srt)">
                  <i data-lucide="file-text"></i>
                  <span>SRT</span>
                </a>
              ` : `
                <button class="btn btn-primary btn-sm" onclick="renderSingleClip('${c.id}')" ${isRendering ? 'disabled' : ''}>
                  <i data-lucide="${isRendering ? 'loader-2' : 'video'}" class="${isRendering ? 'spin' : ''}"></i>
                  <span>${isRendering ? 'Rendering 9:16...' : 'Render Short (9:16)'}</span>
                </button>
              `}
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  lucide.createIcons();
}

function escapeQuotes(str) {
  if (!str) return "";
  return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function seekVideo(sec) {
  const video = document.getElementById("sourceVideoPlayer");
  video.currentTime = sec;
  video.play();
}

// Interactive Operations
async function createDemoProject() {
  const btn = document.getElementById("btnDemo");
  const origText = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i> Creating Demo...`;
  btn.disabled = true;
  lucide.createIcons();

  try {
    const res = await fetch("/api/projects/demo", { method: "POST" });
    if (!res.ok) throw new Error("Failed to create demo project");
    const detail = await res.json();
    showToast("Instant Demo project loaded successfully!");
    await loadProjects();
    selectProject(detail.project.id);
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
    lucide.createIcons();
  }
}

async function renderSingleClip(candidateId) {
  const card = document.getElementById(`card-${candidateId}`);
  if (card) {
    const btn = card.querySelector(".candidate-card-footer button");
    if (btn) {
      btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i> <span>Rendering 9:16...</span>`;
      btn.disabled = true;
      lucide.createIcons();
    }
  }

  const captionStyle = document.getElementById("configCaptionStyle") ? document.getElementById("configCaptionStyle").value : "modern-box";

  try {
    const res = await fetch(`/api/candidates/${candidateId}/render?caption_style=${encodeURIComponent(captionStyle)}`, { method: "POST" });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Rendering failed");
    }
    showToast(`Vertical short rendered with ${captionStyle} captions!`);
    selectProject(state.currentProjectId);
  } catch (err) {
    showToast(err.message, "error");
    selectProject(state.currentProjectId);
  }
}

async function renderBatchClips() {
  if (!state.detail || !state.detail.candidates) return;
  const selected = state.detail.candidates.filter(c => c.selected);
  if (selected.length === 0) {
    showToast("No candidates selected. Change count first.", "error");
    return;
  }

  const captionStyle = document.getElementById("configCaptionStyle") ? document.getElementById("configCaptionStyle").value : "tiktok-viral";

  showToast(`Rendering ${selected.length} short clips with ${captionStyle} captions...`);
  for (const c of selected) {
    try {
      await fetch(`/api/candidates/${c.id}/render?caption_style=${encodeURIComponent(captionStyle)}`, { method: "POST" });
    } catch (e) {
      console.error("Batch clip error", e);
    }
  }
  showToast("All selected clips rendered!");
  selectProject(state.currentProjectId);
}

async function handleTranscribe() {
  if (!state.currentProjectId) return;
  const btn = document.getElementById("btnTranscribe");
  const orig = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i> Transcribing...`;
  btn.disabled = true;
  lucide.createIcons();

  try {
    const res = await fetch(`/api/projects/${state.currentProjectId}/transcribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "local" })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Transcription failed");
    }
    showToast("Transcription completed!");
    selectProject(state.currentProjectId);
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.innerHTML = orig;
    btn.disabled = false;
    lucide.createIcons();
  }
}

async function handleDetectMoments() {
  if (!state.currentProjectId) return;
  const btn = document.getElementById("btnDetectMoments");
  const applyBtn = document.getElementById("btnApplyGenerate");
  const orig = btn ? btn.innerHTML : "";
  if (btn) {
    btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i> Detecting...`;
    btn.disabled = true;
  }
  if (applyBtn) {
    applyBtn.disabled = true;
  }
  lucide.createIcons();

  // Read user configuration
  const clipCount = parseInt(document.getElementById("configClipCount")?.value || "3");
  const durationVal = document.getElementById("configDuration")?.value || "30-60";
  let minDuration = 30.0;
  let maxDuration = 60.0;
  if (durationVal === "15-30") {
    minDuration = 15.0;
    maxDuration = 30.0;
  } else if (durationVal === "60-90") {
    minDuration = 60.0;
    maxDuration = 90.0;
  } else if (durationVal === "10-20") {
    minDuration = 10.0;
    maxDuration = 20.0;
  }

  try {
    // If no transcript yet, auto-transcribe first
    if (!state.detail || !state.detail.transcript) {
      showToast("Step 1/2: Transcribing speech with Whisper...");
      const tRes = await fetch(`/api/projects/${state.currentProjectId}/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "local" })
      });
      if (!tRes.ok) {
        const err = await tRes.json();
        throw new Error(err.detail || "Transcription failed");
      }
    }

    showToast(`Step 2/2: Extracting ${clipCount} viral clips (${minDuration}-${maxDuration}s)...`);
    const res = await fetch(`/api/projects/${state.currentProjectId}/generate-candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clipCount: clipCount,
        minDuration: minDuration,
        maxDuration: maxDuration
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Moment detection failed");
    }
    showToast(`Successfully extracted ${clipCount} viral clips!`);
    selectProject(state.currentProjectId);
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    if (btn) {
      btn.innerHTML = orig;
      btn.disabled = false;
    }
    if (applyBtn) {
      applyBtn.disabled = false;
    }
    lucide.createIcons();
  }
}

// 9:16 Phone Player Modal
function playPhoneClip(candidateId, rank, score, hook, rationale) {
  const modal = document.getElementById("phonePlayerModal");
  const player = document.getElementById("phoneVideoPlayer");
  
  document.getElementById("modalClipRank").textContent = `#${rank}`;
  document.getElementById("modalClipScore").textContent = `${score}% Viral Match`;
  document.getElementById("modalClipHook").textContent = `"${hook}"`;
  document.getElementById("modalClipRationale").textContent = rationale;

  player.src = `/api/media/clips/${candidateId}/stream`;
  document.getElementById("btnDownloadClipModal").href = `/api/media/clips/${candidateId}/download`;
  document.getElementById("btnDownloadSrtModal").href = `/api/media/clips/${candidateId}/subtitles`;

  modal.style.display = "flex";
  player.play();
  lucide.createIcons();
}

function closePhonePlayer() {
  const modal = document.getElementById("phonePlayerModal");
  const player = document.getElementById("phoneVideoPlayer");
  player.pause();
  player.src = "";
  modal.style.display = "none";
}

// Diagnostics & Settings
function updateDiagnosticsUI() {
  if (!state.environment) return;
  const ffmpegEl = document.getElementById("diagFfmpeg");
  const ytdlpEl = document.getElementById("diagYtdlp");

  if (state.environment.hasFfmpeg) {
    ffmpegEl.textContent = "Ready (FFmpeg 7.1 Active)";
    ffmpegEl.className = "badge-success";
  } else {
    ffmpegEl.textContent = "Not Found";
    ffmpegEl.className = "badge-neutral";
  }

  if (state.environment.hasYtdlp) {
    ytdlpEl.textContent = "Installed";
    ytdlpEl.className = "badge-success";
  } else {
    ytdlpEl.textContent = "Optional (install for YouTube imports)";
    ytdlpEl.className = "badge-neutral";
  }
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    document.getElementById("settingLlmProvider").value = data.llmProvider || "deepseek";
    document.getElementById("keyDeepgram").value = data.deepgramApiKey || "";
    document.getElementById("keyDeepseek").value = data.deepseekApiKey || "";
    document.getElementById("keyGemini").value = data.geminiApiKey || "";
    document.getElementById("keyOpenai").value = data.openaiApiKey || "";
    document.getElementById("keyClaude").value = data.anthropicApiKey || "";
    document.getElementById("keyGroq").value = data.groqApiKey || "";
  } catch (e) {
    console.error("Could not load settings", e);
  }
}

async function saveSettings() {
  const payload = {
    llmProvider: document.getElementById("settingLlmProvider").value,
    deepgramApiKey: document.getElementById("keyDeepgram").value,
    deepseekApiKey: document.getElementById("keyDeepseek").value,
    geminiApiKey: document.getElementById("keyGemini").value,
    openaiApiKey: document.getElementById("keyOpenai").value,
    anthropicApiKey: document.getElementById("keyClaude").value,
    groqApiKey: document.getElementById("keyGroq").value
  };

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Failed to save settings");
    showToast("Settings updated successfully!");
    document.getElementById("settingsModal").style.display = "none";
    fetchEnvironment();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Upload & Drag-Drop Handling
function setupUploadHandlers() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const submitBtn = document.getElementById("btnSubmitUpload");

  dropZone.onclick = () => fileInput.click();

  dropZone.ondragover = (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  };
  dropZone.ondragleave = () => dropZone.classList.remove("dragover");
  dropZone.ondrop = (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  fileInput.onchange = () => {
    if (fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  };

  function handleFileSelected(file) {
    state.selectedFile = file;
    dropZone.innerHTML = `
      <i data-lucide="check-circle" class="drop-icon" style="color: var(--color-success)"></i>
      <h4>${file.name}</h4>
      <p>${(file.size / (1024 * 1024)).toFixed(1)} MB ready to upload</p>
    `;
    lucide.createIcons();
    submitBtn.disabled = false;
  }

  submitBtn.onclick = () => {
    if (!state.selectedFile) return;
    uploadFile(state.selectedFile);
  };
}

function uploadFile(file) {
  const progressBox = document.getElementById("uploadProgressContainer");
  const progressBar = document.getElementById("uploadProgressBar");
  const percentText = document.getElementById("uploadPercent");
  const submitBtn = document.getElementById("btnSubmitUpload");
  const captionStyle = document.getElementById("captionStyleSelect").value;

  progressBox.style.display = "flex";
  submitBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("captionStyle", captionStyle);
  formData.append("transcriptionMode", "cloud");

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/projects/upload", true);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = `${pct}%`;
      percentText.textContent = `${pct}%`;
    }
  };

  xhr.onload = async () => {
    if (xhr.status === 200) {
      const project = JSON.parse(xhr.responseText);
      showToast("Media uploaded successfully!");
      document.getElementById("uploadModal").style.display = "none";
      await loadProjects();
      selectProject(project.id);
    } else {
      showToast("Upload failed: " + xhr.responseText, "error");
    }
    submitBtn.disabled = false;
    progressBox.style.display = "none";
  };

  xhr.onerror = () => {
    showToast("Network error during upload", "error");
    submitBtn.disabled = false;
    progressBox.style.display = "none";
  };

  xhr.send(formData);
}

// Event Listeners Initialization
document.addEventListener("DOMContentLoaded", () => {
  fetchEnvironment();
  loadProjects();

  // Top Nav Buttons
  document.getElementById("btnDemo").onclick = createDemoProject;
  document.getElementById("cardDemo").onclick = createDemoProject;

  document.getElementById("btnNewProject").onclick = () => {
    document.getElementById("uploadModal").style.display = "flex";
  };
  document.getElementById("cardUpload").onclick = () => {
    document.getElementById("uploadModal").style.display = "flex";
  };

  document.getElementById("btnYoutube").onclick = () => {
    document.getElementById("youtubeModal").style.display = "flex";
  };
  document.getElementById("cardYoutube").onclick = () => {
    document.getElementById("youtubeModal").style.display = "flex";
  };

  document.getElementById("btnSettings").onclick = () => {
    loadSettings();
    document.getElementById("settingsModal").style.display = "flex";
  };

  // Modal Closers
  document.getElementById("btnCloseUpload").onclick = () => {
    document.getElementById("uploadModal").style.display = "none";
  };
  document.getElementById("btnCancelUpload").onclick = () => {
    document.getElementById("uploadModal").style.display = "none";
  };

  document.getElementById("btnCloseYoutube").onclick = () => {
    document.getElementById("youtubeModal").style.display = "none";
  };
  document.getElementById("btnCancelYoutube").onclick = () => {
    document.getElementById("youtubeModal").style.display = "none";
  };

  document.getElementById("btnCloseSettings").onclick = () => {
    document.getElementById("settingsModal").style.display = "none";
  };
  document.getElementById("btnCancelSettings").onclick = () => {
    document.getElementById("settingsModal").style.display = "none";
  };
  document.getElementById("btnSaveSettings").onclick = saveSettings;

  document.getElementById("btnClosePhonePlayer").onclick = closePhonePlayer;

  // Workspace Action Buttons
  document.getElementById("btnTranscribe").onclick = handleTranscribe;
  document.getElementById("btnDetectMoments").onclick = handleDetectMoments;
  const btnApply = document.getElementById("btnApplyGenerate");
  if (btnApply) btnApply.onclick = handleDetectMoments;
  document.getElementById("btnRenderBatch").onclick = renderBatchClips;

  document.getElementById("btnRenameProject").onclick = async () => {
    if (!state.currentProjectId) return;
    const currentName = state.detail.project.name || "";
    const newName = prompt("Enter new project title:", currentName);
    if (newName && newName.trim()) {
      await fetch(`/api/projects/${state.currentProjectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() })
      });
      await loadProjects();
      selectProject(state.currentProjectId);
    }
  };

  document.getElementById("btnDeleteProject").onclick = async () => {
    if (!state.currentProjectId) return;
    if (confirm("Are you sure you want to delete this project and all its clips?")) {
      await fetch(`/api/projects/${state.currentProjectId}`, { method: "DELETE" });
      showToast("Project deleted");
      state.detail = null;
      state.currentProjectId = null;
      await loadProjects();
      renderWorkspace();
    }
  };

  const clipCountEl = document.getElementById("configClipCount");
  if (clipCountEl) {
    clipCountEl.onchange = async (e) => {
      if (!state.currentProjectId) return;
      const count = parseInt(e.target.value);
      await fetch(`/api/projects/${state.currentProjectId}/select-count`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count })
      });
      selectProject(state.currentProjectId);
    };
  }

  // YouTube Submission
  document.getElementById("btnSubmitYoutube").onclick = async () => {
    const url = document.getElementById("youtubeUrlInput").value.trim();
    if (!url) {
      showToast("Please enter a valid YouTube URL", "error");
      return;
    }
    const statusBox = document.getElementById("ytStatusBox");
    statusBox.style.display = "block";
    statusBox.textContent = "Downloading YouTube video with yt-dlp... this may take 30-60 seconds.";

    try {
      const res = await fetch("/api/projects/youtube", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Download failed");
      }
      const project = await res.json();
      showToast("YouTube video imported successfully!");
      document.getElementById("youtubeModal").style.display = "none";
      await loadProjects();
      selectProject(project.id);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      statusBox.style.display = "none";
    }
  };

  setupUploadHandlers();
  lucide.createIcons();
});
