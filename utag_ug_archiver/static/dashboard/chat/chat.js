// UTAG WhatsApp-style Chat JavaScript

function initThreadChat(options) {
    const container = document.querySelector(options.containerSelector);
    const form = document.querySelector(options.formSelector);
    const messageList = document.querySelector(options.listSelector);
    const messagesScroll = document.getElementById('utag-messages-scroll');
    const messageInput = document.getElementById('utag-message-input');

    if (!container || !form || !messageList) {
        console.warn('Chat initialization failed: required elements not found');
        return;
    }

    const threadId = container.getAttribute('data-thread-id');
    const currentUserId = container.getAttribute('data-current-user');

    // Auto-resize textarea
    if (messageInput) {
        messageInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        // Submit on Enter (but Shift+Enter for new line)
        messageInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
            }
        });
    }

    // Scroll to bottom on load
    function scrollToBottom(smooth = false) {
        if (messagesScroll) {
            messagesScroll.scrollTo({
                top: messagesScroll.scrollHeight,
                behavior: smooth ? 'smooth' : 'auto'
            });
        }
    }

    // Initial scroll to bottom
    scrollToBottom(false);

    // Handle form submission
    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(form);
        const messageText = formData.get('body');

        if (!messageText || !messageText.trim()) {
            return;
        }

        // Disable submit button during send
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalBtnHTML = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i>';

        // Send message via AJAX
        fetch(form.action || window.location.href, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Add message to list
                    const messageItem = createMessageElement(data.message);
                    messageList.appendChild(messageItem);

                    // Clear input
                    messageInput.value = '';
                    messageInput.style.height = 'auto';

                    // Scroll to new message
                    scrollToBottom(true);

                    // Focus back on input
                    messageInput.focus();
                } else {
                    alert('Failed to send message: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error sending message:', error);
                alert('Failed to send message. Please try again.');
            })
            .finally(() => {
                // Re-enable submit button
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHTML;
            });
    });

    // Create message element
    function createMessageElement(message) {
        const li = document.createElement('li');
        li.className = `utag-message-item ${message.sender_id === parseInt(currentUserId) ? 'sent' : 'received'}`;
        li.setAttribute('data-message-id', message.id);

        const bubble = document.createElement('div');
        bubble.className = 'utag-message-bubble';

        const text = document.createElement('p');
        text.className = 'utag-message-text';
        text.textContent = message.body;

        const meta = document.createElement('div');
        meta.className = 'utag-message-meta';

        const time = document.createElement('span');
        time.className = 'utag-message-time';
        time.textContent = formatTime(new Date(message.created_at));

        meta.appendChild(time);

        if (message.sender_id === parseInt(currentUserId)) {
            const status = document.createElement('span');
            status.className = 'utag-message-status';
            status.innerHTML = '<i class="mdi mdi-check"></i>';
            meta.appendChild(status);
        }

        bubble.appendChild(text);
        bubble.appendChild(meta);
        li.appendChild(bubble);

        return li;
    }

    // Format time as HH:MM
    function formatTime(date) {
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    // WebSocket connection for real-time messages (if Channels is set up)
    function initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${threadId}/`;

        try {
            const socket = new WebSocket(wsUrl);

            socket.onopen = function (e) {
                console.log('WebSocket connection established');
            };

            socket.onmessage = function (e) {
                const data = JSON.parse(e.data);

                if (data.type === 'chat_message') {
                    // Only add if from other user
                    if (data.message.sender_id !== parseInt(currentUserId)) {
                        const messageItem = createMessageElement(data.message);
                        messageList.appendChild(messageItem);
                        scrollToBottom(true);

                        // Play notification sound (optional)
                        playNotificationSound();
                    }
                } else if (data.type === 'message_read') {
                    // Update read receipts
                    updateReadReceipt(data.message_id);
                }
            };

            socket.onclose = function (e) {
                console.log('WebSocket connection closed, attempting to reconnect...');
                setTimeout(initWebSocket, 3000);
            };

            socket.onerror = function (e) {
                console.error('WebSocket error:', e);
            };

            return socket;
        } catch (error) {
            console.warn('WebSocket not available:', error);
            return null;
        }
    }

    // Update read receipt icon
    function updateReadReceipt(messageId) {
        const messageItem = messageList.querySelector(`[data-message-id="${messageId}"]`);
        if (messageItem) {
            const statusIcon = messageItem.querySelector('.utag-message-status i');
            if (statusIcon) {
                statusIcon.className = 'mdi mdi-check-all';
            }
        }
    }

    // Play notification sound
    function playNotificationSound() {
        // Simple beep - can be replaced with actual sound file
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSp9y/LZkEkLElyx4+mpVRQLRJzg8r1rHwYqfcz04JZJDhNcsuPnpHQwCzCD0fPYhzgIHm/E8+OSVBEIRZvi87dcGAQ2idbz0HskBSl+0O/UtmgbBSZ4yPLLeysMJHfH8NyQQAoUXrPq66hUFApGnt/yvmwhBSl9y/HZkEgKE1yw4+epVBQKRp3g8r1rIAUqfMzz35VJDRNcsuLnp3QwCy+Cz/PZhzgJHm7F8+STUxAIRZvi8rddGQU1iNXzz3wkBSl+0O/VtmgbBSV4yPLMeywLJXfG8NyQQAoUXrPq66hUFApGnt/yvmwhBSl9y/HZkEgKE1yw4+epVBQKRp3g8r1rIAUpfcvz35VJDRNcsuLnp3MwCy+Cz/PYhzgJHm7F8+STUxAIRZvi8rddGQU1iNXzz3wkBCh+0O/Vtmcb');
        audio.volume = 0.3;
        audio.play().catch(e => console.log('Audio play failed:', e));
    }

    // Try to initialize WebSocket
    const socket = initWebSocket();

    // Return public API
    return {
        scrollToBottom,
        socket
    };
}

// Auto-initialize if elements are present
document.addEventListener('DOMContentLoaded', function () {
    const chatApp = document.getElementById('thread-chat-app');
    if (chatApp) {
        // Will be initialized by inline script in template
    }
});
