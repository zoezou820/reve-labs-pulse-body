const form = document.getElementById('render-form');
const output = document.getElementById('output');
const audio = document.getElementById('audio');
const trackTitle = document.getElementById('track-title');

audio.addEventListener('change', () => {
  const file = audio.files[0];
  if (!file) return;
  const title = file.name.replace(/\.[^.]+$/, '').replace(/^\d+[\s_-]*/, '').replace(/[_-]+/g, ' ').trim();
  if (title) trackTitle.value = title;
});

function eta(seconds) {
  if (!Number.isFinite(seconds)) return 'Estimating';
  if (seconds < 60) return `${Math.ceil(seconds)}s left`;
  return `${Math.floor(seconds / 60)}m ${Math.ceil(seconds % 60)}s left`;
}

function showProgress(data) {
  const percent = Math.round((data.progress || 0) * 100);
  output.innerHTML = `<div class="status"><div>${data.message || 'Rendering...'}</div><div class="progress"><div style="width:${percent}%"></div></div><div class="progress-meta"><span>${percent}%</span><span>${eta(data.eta_seconds)}</span></div></div>`;
}

async function poll(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  const data = await response.json();
  if (data.status === 'error') throw new Error(data.error || 'Render failed.');
  if (data.status === 'done') {
    output.innerHTML = `<video controls autoplay src="${data.video_url}"></video><p class="download"><a href="${data.video_url}" download>Download MP4</a></p>`;
    return;
  }
  showProgress(data);
  setTimeout(() => poll(jobId).catch(showError), 1200);
}

function showError(error) {
  output.innerHTML = `<p class="status error">${error.message || error}</p>`;
  form.querySelector('button').disabled = false;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = form.querySelector('button');
  button.disabled = true;
  showProgress({progress: 0, message: 'Uploading audio...'});
  try {
    const response = await fetch('/api/render', {method: 'POST', body: new FormData(form)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not start render.');
    await poll(data.job_id);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
});
