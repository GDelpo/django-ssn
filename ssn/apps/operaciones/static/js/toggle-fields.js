/**
 * Inicializa un toggle genérico: muestra/oculta los "dependentIds" según shouldShowFn.
 * @param {Object} config
 * @param {string} config.triggerId         - ID del elemento disparador (ej: "id_tipo_especie").
 * @param {string[]} config.dependentIds    - IDs de los campos a mostrar/ocultar.
 * @param {string[]} [config.triggerIdsAlt] - IDs adicionales que influyen (ej: ["id_tipo_valuacion"]).
 * @param {function(string, ...string): boolean} config.shouldShowFn 
 *        - Función que recibe el valor del trigger principal y de los secundarios, devuelve true/false.
 * @param {boolean} [config.highlight=true] - Si aplica animación de fondo breve.
 */
function initToggleFields({ triggerId, dependentIds, triggerIdsAlt = [], shouldShowFn, highlight = true }) {
  const triggerEl = document.getElementById(triggerId);
  if (!triggerEl) return;

  // Elementos “dependientes”
  const dependentEls = dependentIds
    .map(id => document.getElementById(id))
    .filter(el => !!el);

  // Triggers secundarios
  const altEls = triggerIdsAlt
    .map(id => document.getElementById(id))
    .filter(el => !!el);

  /**
   * Aplica animación para mostrar u ocultar un contenedor padre
   * @param {HTMLElement} containerEl - div padre del input
   * @param {boolean} show           - true → mostrar, false → ocultar
   */
  function setVisibility(containerEl, show) {
    if (!containerEl) return;
    containerEl.style.transition = 'max-height 0.5s ease, opacity 0.5s ease, transform 0.5s ease';
    containerEl.style.overflow   = 'hidden';

    if (show) {
      containerEl.style.display = '';
      setTimeout(() => {
        containerEl.style.maxHeight = '100px';
        containerEl.style.opacity   = '1';
        containerEl.style.transform = 'translateY(0)';
        containerEl.classList.add('bg-yellow-50');
        setTimeout(() => containerEl.classList.remove('bg-yellow-50'), 1000);
      }, 10);
    } else {
      containerEl.style.maxHeight = '0';
      containerEl.style.opacity   = '0';
      containerEl.style.transform = 'translateY(-10px)';
      setTimeout(() => {
        containerEl.style.display = 'none';
      }, 500);
    }
  }

  /**
   * Evalúa shouldShowFn con los valores del trigger y secundarios.
   */
  function toggle() {
    const triggerVal = triggerEl.value.trim().toUpperCase();
    const altVals = altEls.map(el => el.value.trim().toUpperCase());
    const show = shouldShowFn(triggerVal, ...altVals);

    dependentEls.forEach(depEl => {
      const container = depEl.closest('div');
      setVisibility(container, show);
      depEl.disabled = !show;
      //if (!show) depEl.value = '';
    });
  }

  // Estado inicial
  toggle();

  // Listener cambio en trigger principal
  triggerEl.addEventListener('change', () => {
    toggle();
    if (highlight) {
      const parent = triggerEl.closest('div');
      if (parent) {
        parent.classList.add('bg-blue-50');
        setTimeout(() => parent.classList.remove('bg-blue-50'), 800);
      }
    }
  });

  // Listeners en triggers secundarios
  altEls.forEach(elAlt => {
    elAlt.addEventListener('change', () => {
      toggle();
      if (highlight) {
        const parent = elAlt.closest('div');
        if (parent) {
          parent.classList.add('bg-blue-50');
          setTimeout(() => parent.classList.remove('bg-blue-50'), 800);
        }
      }
    });
  });
}
