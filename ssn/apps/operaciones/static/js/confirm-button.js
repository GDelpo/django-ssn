/**
 * Muestra un confirm() en los elementos que coincidan con selector.
 * @param {string} selector - CSS selector (ej: "#sendEmptyBtn" o ".btn-confirm").
 * @param {string} message  - Texto del confirm().
 */
function initConfirmButton(selector, message) {
  const btns = document.querySelectorAll(selector);
  if (!btns.length) return;
  btns.forEach(btn => {
    btn.addEventListener('click', e => {
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });
}
