const TELEGRAM_BOT_TOKEN = 'PASTE_YOUR_TELEGRAM_BOT_TOKEN';
const TELEGRAM_CHAT_ID = 'PASTE_YOUR_CHAT_ID';

const form = document.getElementById('checkoutForm');
const formMessage = document.getElementById('formMessage');
const glow = document.querySelector('.cursor-glow');
const revealEls = document.querySelectorAll('.reveal');

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.2 }
);

revealEls.forEach((el) => observer.observe(el));

window.addEventListener('pointermove', (event) => {
  glow.style.left = `${event.clientX}px`;
  glow.style.top = `${event.clientY}px`;
});

function setMessage(text, status = 'success') {
  formMessage.textContent = text;
  formMessage.className = `form-message ${status}`;
}

function validateForm(data) {
  const requiredFields = ['fullName', 'email', 'phone', 'address', 'orderRef'];
  for (const key of requiredFields) {
    if (!data[key] || !data[key].trim()) {
      return `${key} is required.`;
    }
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(data.email.trim())) {
    return 'Please enter a valid email address.';
  }

  return '';
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const formData = Object.fromEntries(new FormData(form).entries());
  const validationError = validateForm(formData);

  if (validationError) {
    setMessage(validationError, 'error');
    return;
  }

  if (
    TELEGRAM_BOT_TOKEN === 'PASTE_YOUR_TELEGRAM_BOT_TOKEN' ||
    TELEGRAM_CHAT_ID === 'PASTE_YOUR_CHAT_ID'
  ) {
    setMessage('Add your Telegram bot token and chat ID in script.js first.', 'error');
    return;
  }

  const text = [
    '🛒 New Order Details',
    `Name: ${formData.fullName}`,
    `Email: ${formData.email}`,
    `Phone: ${formData.phone}`,
    `Address: ${formData.address}`,
    `Payment Reference: ${formData.orderRef}`,
    `Submitted At: ${new Date().toISOString()}`,
  ].join('\n');

  const endpoint = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TELEGRAM_CHAT_ID,
        text,
      }),
    });

    if (!response.ok) {
      throw new Error('Telegram API error');
    }

    setMessage('Order details sent successfully.', 'success');
    form.reset();
  } catch {
    setMessage('Failed to send details. Please check Telegram settings.', 'error');
  }
});
