
/**
 * Copia al portapapeles el contenido de "sourceId" cuando se clickea "buttonId".
 * @param {string} buttonId   - ID del botón que dispara la copia.
 * @param {string} sourceId   - ID del elemento cuyo texto se copia.
 * @param {string} successMsg - Mensaje de éxito (alert).
 * @param {string} errorMsg   - Prefijo de mensaje de error (alert).
 */
function initCopyToClipboard(buttonId, sourceId, successMsg, errorMsg = 'Error al copiar: ') {
  const btn = document.getElementById(buttonId);
  const src = document.getElementById(sourceId);
  if (!btn || !src) return;

  btn.addEventListener('click', () => {
    const text = src.innerText;
    navigator.clipboard.writeText(text)
      .then(() => alert(successMsg))
      .catch(err => alert(errorMsg + err));
  });
}
