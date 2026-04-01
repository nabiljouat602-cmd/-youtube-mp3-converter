// DOM Elements
const urlInput = document.getElementById('url');
const convertBtn = document.getElementById('convertBtn');
const clearBtn = document.getElementById('clearBtn');
const previewCard = document.getElementById('previewCard');
const statusCard = document.getElementById('statusCard');
const downloadCard = document.getElementById('downloadCard');
const statusTitle = document.getElementById('statusTitle');
const statusMessage = document.getElementById('statusMessage');
const downloadLink = document.getElementById('downloadLink');
const downloadSongTitle = document.getElementById('downloadSongTitle');
const fileSizeSpan = document.getElementById('fileSize');
const thumbnail = document.getElementById('thumbnail');
const videoTitle = document.getElementById('videoTitle');
const channelName = document.getElementById('channelName');
const durationBadge = document.getElementById('durationBadge');

// Update status function
function updateStatus(type, title, message, isProcessing = false) {
    const statusIcon = statusCard.querySelector('.status-icon i');
    
    if (type === 'processing') {
        statusIcon.className = 'fas fa-spinner fa-pulse';
        statusTitle.textContent = title || 'Processing...';
        statusMessage.textContent = message || 'Downloading and converting your video. Please wait...';
        statusCard.style.borderLeftColor = '#f59e0b';
    } else if (type === 'success') {
        statusIcon.className = 'fas fa-check-circle';
        statusTitle.textContent = title || 'Conversion Complete!';
        statusMessage.textContent = message || 'Your MP3 file is ready to download';
        statusCard.style.borderLeftColor = '#10b981';
    } else if (type === 'error') {
        statusIcon.className = 'fas fa-exclamation-triangle';
        statusTitle.textContent = title || 'Error';
        statusMessage.textContent = message || 'Something went wrong. Please try again.';
        statusCard.style.borderLeftColor = '#ef4444';
    } else {
        statusIcon.className = 'fas fa-music';
        statusTitle.textContent = title || 'Ready to Convert';
        statusMessage.textContent = message || 'Paste a YouTube URL and click the convert button';
        statusCard.style.borderLeftColor = '#ff0000';
    }
}

// Show video preview
async function showPreview(url) {
    try {
        const response = await fetch('/api/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.success && data.info) {
            thumbnail.src = data.info.thumbnail || 'https://via.placeholder.com/160x90?text=No+Thumbnail';
            videoTitle.textContent = data.info.title || 'Unknown Title';
            channelName.textContent = data.info.uploader || 'Unknown Channel';
            durationBadge.textContent = data.info.duration_formatted || '0:00';
            previewCard.classList.remove('hidden');
        } else {
            previewCard.classList.add('hidden');
        }
    } catch (error) {
        console.error('Preview error:', error);
        previewCard.classList.add('hidden');
    }
}

// Clear input
clearBtn.addEventListener('click', () => {
    urlInput.value = '';
    clearBtn.style.display = 'none';
    previewCard.classList.add('hidden');
    updateStatus('idle');
    downloadCard.classList.add('hidden');
});

// Show/hide clear button and preview
urlInput.addEventListener('input', () => {
    clearBtn.style.display = urlInput.value.length > 0 ? 'flex' : 'none';
    
    if (urlInput.value.length > 0) {
        clearTimeout(window.previewTimeout);
        window.previewTimeout = setTimeout(() => {
            showPreview(urlInput.value.trim());
        }, 500);
    } else {
        previewCard.classList.add('hidden');
        downloadCard.classList.add('hidden');
        updateStatus('idle');
    }
});

// Main conversion function
async function convertToMp3() {
    const url = urlInput.value.trim();
    
    if (!url) {
        updateStatus('error', 'No URL', 'Please enter a YouTube URL');
        urlInput.focus();
        return;
    }
    
    // Validate YouTube URL
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)\/.+/;
    if (!youtubeRegex.test(url)) {
        updateStatus('error', 'Invalid URL', 'Please enter a valid YouTube video URL');
        return;
    }
    
    // Disable button and hide download card
    convertBtn.disabled = true;
    downloadCard.classList.add('hidden');
    
    // Show processing status
    updateStatus('processing', 'Processing Your Request', 'Downloading and converting to MP3 (192kbps). This may take a few moments...', true);
    
    try {
        const response = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Show success status
            updateStatus('success', 'Conversion Complete!', `Successfully converted "${data.info.title}" to MP3`);
            
            // Setup download button
            downloadLink.href = data.download_url;
            downloadSongTitle.textContent = data.info.title;
            fileSizeSpan.innerHTML = `<i class="fas fa-database"></i> ${data.info.size_mb} MB`;
            
            // Show download card with animation
            downloadCard.classList.remove('hidden');
            downloadCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            // Handle error response
            const errorMsg = data.error || 'Conversion failed. Please try again.';
            updateStatus('error', 'Conversion Failed', errorMsg);
            
            // Specific error messages
            if (errorMsg.toLowerCase().includes('private')) {
                updateStatus('error', 'Video Unavailable', 'This video is private or has been removed');
            } else if (errorMsg.toLowerCase().includes('age') || errorMsg.toLowerCase().includes('restricted')) {
                updateStatus('error', 'Age Restricted', 'This video requires age verification and cannot be converted');
            } else if (errorMsg.toLowerCase().includes('geo') || errorMsg.toLowerCase().includes('country')) {
                updateStatus('error', 'Geo-blocked', 'This video is not available in your region');
            }
        }
    } catch (error) {
        console.error('Conversion error:', error);
        
        if (error.message.includes('Failed to fetch') || error.name === 'TypeError') {
            updateStatus('error', 'Connection Error', 'Cannot connect to server. Please make sure the backend is running.');
        } else {
            updateStatus('error', 'Unexpected Error', error.message || 'Something went wrong. Please try again.');
        }
    } finally {
        // Re-enable button
        convertBtn.disabled = false;
    }
}

// Event listeners
convertBtn.addEventListener('click', convertToMp3);

// Enter key support
urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && urlInput.value.trim()) {
        convertToMp3();
    }
});

// Initial status
updateStatus('idle');
console.log('YTMP3 Pro - Ready to convert YouTube videos');