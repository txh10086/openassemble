class AIAssistant {
    constructor() {
        this.isOpen = false;
        this.messages = [];
        this.init();
    }

    init() {
        this.createUI();
        this.bindEvents();
    }

    bindEvents() {
        // 绑定回车键发送消息
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && document.getElementById('chatInput') === document.activeElement) {
                this.sendMessage();
            }
        });
    }

    createUI() {
        const assistantHTML = `
            <div class="ai-assistant-container" id="aiAssistant" style="display: none;">
                <div class="assistant-panel">
                    <div class="assistant-header">
                        <h3>🤖 AI工艺助手</h3>
                        <button onclick="aiAssistant.toggle()" class="close-btn">×</button>
                    </div>
                    <div class="chat-messages" id="chatMessages">
                        <div class="assistant-message">
                            <div class="message-avatar">🤖</div>
                            <div class="message-content">
                                您好！我是AI工艺助手，可以帮您解答工艺流程、设备操作等问题。
                            </div>
                        </div>
                    </div>
                    <div class="chat-input-area">
                        <input type="text" id="chatInput" placeholder="请输入您的问题..." />
                        <button onclick="aiAssistant.sendMessage()" class="send-btn">发送</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', assistantHTML);
    }

    toggle() {
        const assistant = document.getElementById('aiAssistant');
        this.isOpen = !this.isOpen;
        assistant.style.display = this.isOpen ? 'block' : 'none';

        if (this.isOpen) {
            document.getElementById('chatInput').focus();
        }
    }

    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();

        if (!message) return;

        // 显示用户消息
        this.addMessage(message, 'user');
        input.value = '';

        // 显示加载状态
        this.addMessage('正在思考...', 'assistant', true);

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            const data = await response.json();

            // 移除加载消息，添加AI回复
            this.removeLastMessage();
            this.addMessage(data.response, 'assistant');

        } catch (error) {
            this.removeLastMessage();
            this.addMessage('抱歉，我暂时无法回答这个问题。请稍后再试。', 'assistant');
            console.error('AI助手错误:', error);
        }
    }

    addMessage(content, type, isLoading = false) {
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `${type}-message${isLoading ? ' loading' : ''}`;

        const avatar = type === 'user' ? '👤' : '🤖';
        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">${content}</div>
        `;

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    removeLastMessage() {
        const messagesContainer = document.getElementById('chatMessages');
        const lastMessage = messagesContainer.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('loading')) {
            lastMessage.remove();
        }
    }
}

// 确保DOM加载完成后再初始化
document.addEventListener('DOMContentLoaded', function() {
    window.aiAssistant = new AIAssistant();
});

// 如果DOM已经加载完成，立即初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        window.aiAssistant = new AIAssistant();
    });
} else {
    window.aiAssistant = new AIAssistant();
}