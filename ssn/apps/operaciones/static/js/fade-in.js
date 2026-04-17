/**
 * Aplica animación "fade-in" a todos los elementos que coincidan con selector,
 * escalonando la aparición con delayStep ms entre cada uno.
 * @param {string} selector  - CSS selector (ej: ".bg-white\\/70").
 * @param {number} delayStep - Retardo en ms entre cada elemento (por índice).
 */
function initFadeIn(selector, delayStep = 200) {
  const els = document.querySelectorAll(selector);
  els.forEach((el, idx) => {
    setTimeout(() => {
      el.classList.add('animate-fadeIn');
    }, idx * delayStep);
  });
}
