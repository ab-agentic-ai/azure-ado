import { marked } from 'marked';
import DOMPurify from 'dompurify';

const vscode = acquireVsCodeApi();
const conversation = document.getElementById('conversation');
const messagesEl = document.getElementById('messages');
const noticesEl = document.getElementById('notices');
const input = document.getElementById('message-input');
const sendButton = document.getElementById('send');
const cancelButton = document.getElementById('cancel');
const agentSelect = document.getElementById('agent-select');
const authButton = document.getElementById('auth-button');
const statusDot = document.getElementById('connection-status');
const attachmentsEl = document.getElementById('attachments');
let selectedAgentId = '';
let attachedItems = [];
let currentAssistant = null;
let currentAssistantText = '';
const renderingVersions = new WeakMap();
let busy = false;

function createMessage(role, text, attachmentLabels = []) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = role === 'assistant' ? 'AChat' : 'You';
  const body = document.createElement('div');
  body.className = 'message-body';
  if (role === 'assistant') {
    renderMarkdown(body, text);
  } else {
    const content = document.createElement('p');
    content.textContent = text;
    body.append(content);
    if (attachmentLabels.length) {
      const attached = document.createElement('div');
      attached.className = 'sent-attachments';
      attached.textContent = `Attached: ${attachmentLabels.join(', ')}`;
      body.append(attached);
    }
  }
  article.append(label, body);
  messagesEl.append(article);
  conversation.scrollTop = conversation.scrollHeight;
  return body;
}

async function renderMarkdown(target, markdown) {
  const renderId = (renderingVersions.get(target) || 0) + 1;
  renderingVersions.set(target, renderId);
  const html = await marked.parse(markdown, { breaks: true, gfm: true });
  if (renderId !== renderingVersions.get(target) || !target.isConnected) return;
  target.innerHTML = DOMPurify.sanitize(html, {
    FORBID_TAGS: ['img', 'iframe', 'video', 'audio', 'form', 'input', 'button'],
    FORBID_ATTR: ['style', 'onerror', 'onclick'],
  });
  for (const code of target.querySelectorAll('pre code')) {
    const source = code.textContent || '';
    const lines = source.replace(/\n$/, '').split('\n');
    code.replaceChildren();
    lines.forEach((line, index) => {
      const row = document.createElement('span');
      row.className = 'code-line';
      const number = document.createElement('span');
      number.className = 'line-number';
      number.textContent = String(index + 1);
      const text = document.createElement('span');
      text.className = 'line-text';
      text.textContent = line || ' ';
      row.append(number, text);
      code.append(row);
    });
  }
  conversation.scrollTop = conversation.scrollHeight;
}

function showNotice(message, level = 'info') {
  const notice = document.createElement('div');
  notice.className = `notice ${level}`;
  notice.textContent = message;
  noticesEl.append(notice);
  conversation.scrollTop = conversation.scrollHeight;
  window.setTimeout(() => notice.remove(), 9000);
}

function setBusy(value) {
  busy = value;
  sendButton.disabled = value;
  input.disabled = value;
  cancelButton.hidden = !value;
  sendButton.textContent = value ? '…' : '↑';
}

function renderAttachments(items, totalChars, maxChars) {
  attachedItems = items;
  attachmentsEl.replaceChildren();
  attachmentsEl.hidden = items.length === 0;
  for (const item of items) {
    const chip = document.createElement('div');
    chip.className = 'attachment-chip';
    const label = document.createElement('span');
    label.textContent = `${item.path}${item.truncated ? ' (shortened)' : ''}`;
    const remove = document.createElement('button');
    remove.className = 'remove-attachment';
    remove.type = 'button';
    remove.title = `Remove ${item.path}`;
    remove.setAttribute('aria-label', `Remove ${item.path}`);
    remove.textContent = '×';
    remove.addEventListener('click', () => vscode.postMessage({ type: 'removeAttachment', id: item.id }));
    chip.append(label, remove);
    attachmentsEl.append(chip);
  }
  if (items.length) {
    const count = document.createElement('div');
    count.className = 'context-count';
    count.textContent = `${Number(totalChars).toLocaleString()} / ${Number(maxChars).toLocaleString()} chars`;
    attachmentsEl.append(count);
  }
}

function setAgents(agents, preferredId, signedIn) {
  agentSelect.replaceChildren();
  const options = Array.isArray(agents) ? agents : [];
  for (const agent of options) {
    const option = document.createElement('option');
    option.value = agent.id;
    const isAdo = /devops|azure/i.test(`${agent.name} ${agent.id}`);
    option.textContent = isAdo ? `${agent.name} · ADO` : agent.name;
    option.title = agent.description || agent.name;
    agentSelect.append(option);
  }
  selectedAgentId = options.some((agent) => agent.id === preferredId) ? preferredId : options[0]?.id || '';
  agentSelect.value = selectedAgentId;
  agentSelect.disabled = options.length === 0;
  authButton.textContent = signedIn ? 'Sign out' : 'Sign in';
  authButton.dataset.action = signedIn ? 'signOut' : 'signIn';
  statusDot.classList.toggle('connected', signedIn);
  statusDot.title = signedIn ? 'Connected to AChat' : 'Not connected';
  document.getElementById('welcome').hidden = messagesEl.children.length > 0;
}

function sendMessage() {
  if (busy) return;
  const text = input.value.trim();
  if (!text) return;
  const labels = attachedItems.map((item) => item.path);
  createMessage('user', text, labels);
  document.getElementById('welcome').hidden = true;
  input.value = '';
  input.style.height = '';
  setBusy(true);
  currentAssistant = null;
  currentAssistantText = '';
  vscode.postMessage({ type: 'send', text, agentId: selectedAgentId });
}

document.getElementById('attach-selection').addEventListener('click', () => vscode.postMessage({ type: 'attachSelection' }));
document.getElementById('attach-file').addEventListener('click', () => vscode.postMessage({ type: 'attachFile' }));
document.getElementById('refresh-agents').addEventListener('click', () => vscode.postMessage({ type: 'refreshAgents' }));
document.getElementById('new-chat').addEventListener('click', () => vscode.postMessage({ type: 'newChat' }));
agentSelect.addEventListener('change', () => {
  selectedAgentId = agentSelect.value;
  vscode.postMessage({ type: 'selectAgent', agentId: selectedAgentId });
});
authButton.addEventListener('click', () => vscode.postMessage({ type: authButton.dataset.action }));
sendButton.addEventListener('click', sendMessage);
cancelButton.addEventListener('click', () => vscode.postMessage({ type: 'cancel' }));
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
});
document.querySelectorAll('.quick-prompts button').forEach((button) => button.addEventListener('click', () => {
  input.value = button.dataset.prompt || '';
  input.focus();
}));

window.addEventListener('message', (event) => {
  const message = event.data || {};
  switch (message.type) {
    case 'agents':
      setAgents(message.agents, message.selectedAgentId, message.signedIn);
      break;
    case 'attachments':
      renderAttachments(message.items || [], message.totalChars || 0, message.maxChars || 0);
      break;
    case 'streamStart':
      currentAssistant = createMessage('assistant', '');
      currentAssistant.classList.add('streaming');
      currentAssistantText = '';
      break;
    case 'delta':
      currentAssistantText += message.text || '';
      if (currentAssistant) void renderMarkdown(currentAssistant, currentAssistantText);
      break;
    case 'complete':
      currentAssistant?.parentElement?.classList.remove('streaming');
      if (currentAssistant && Array.isArray(message.actions) && message.actions.length) {
        const actions = document.createElement('div');
        actions.className = 'proposal-actions';
        for (const action of message.actions) {
          if (!action || typeof action.id !== 'string') continue;
          const button = document.createElement('button');
          button.type = 'button';
          button.className = action.kind === 'edit' ? 'proposal-edit' : 'proposal-command';
          button.dataset.actionId = action.id;
          button.textContent = action.kind === 'edit' ? 'Review and apply changes' : 'Review command';
          button.addEventListener('click', () => {
            button.disabled = true;
            vscode.postMessage({ type: 'reviewAction', id: action.id });
          }, { once: true });
          actions.append(button);
        }
        currentAssistant.append(actions);
      }
      currentAssistant = null;
      currentAssistantText = '';
      setBusy(false);
      break;
    case 'cancelled':
    case 'error':
      if (currentAssistant && !currentAssistantText) currentAssistant.parentElement?.remove();
      else currentAssistant?.parentElement?.classList.remove('streaming');
      currentAssistant = null;
      currentAssistantText = '';
      setBusy(false);
      showNotice(message.text || 'AChat request failed.', message.type === 'error' ? 'error' : 'info');
      break;
    case 'notice':
      showNotice(message.text || '', message.level || 'info');
      break;
    case 'actionResult': {
      const button = document.querySelector(`[data-action-id="${CSS.escape(message.id || '')}"]`);
      if (button instanceof HTMLButtonElement) {
        if (message.completed) button.remove();
        else button.disabled = false;
      }
      break;
    }
    case 'clear':
      messagesEl.replaceChildren();
      noticesEl.replaceChildren();
      document.getElementById('welcome').hidden = false;
      break;
  }
});

vscode.postMessage({ type: 'ready' });
