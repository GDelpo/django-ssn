/**
 * Sistema de alertas colapsables
 * Después de un tiempo, colapsa las alertas en una barra compacta.
 * Al hacer clic, se vuelven a expandir.
 */

const AlertsCollapse = {
  config: {
    collapseDelay: 5000, // 5 segundos
    containerId: 'alerts-container',
    expandedId: 'alerts-expanded-view',
    collapsedId: 'alerts-collapsed-bar',
  },

  /**
   * Inicializa el sistema de alertas colapsables
   */
  init() {
    const container = document.getElementById(this.config.containerId);
    if (!container) return;

    const expandedView = document.getElementById(this.config.expandedId);
    const collapsedBar = document.getElementById(this.config.collapsedId);
    
    if (!expandedView || !collapsedBar) return;

    // Configurar eventos de clic
    collapsedBar.addEventListener('click', () => this.expand());
    
    // Auto-colapsar después del delay
    this.collapseTimeout = setTimeout(() => this.collapse(), this.config.collapseDelay);

    // Si el usuario interactúa, cancelar el auto-colapso
    expandedView.addEventListener('mouseenter', () => {
      if (this.collapseTimeout) {
        clearTimeout(this.collapseTimeout);
        this.collapseTimeout = null;
      }
    });

    // Reiniciar el timer cuando el mouse sale
    expandedView.addEventListener('mouseleave', () => {
      if (!this.isCollapsed) {
        this.collapseTimeout = setTimeout(() => this.collapse(), this.config.collapseDelay);
      }
    });

    this.isCollapsed = false;
  },

  /**
   * Colapsa las alertas en la barra compacta
   */
  collapse() {
    const expandedView = document.getElementById(this.config.expandedId);
    const collapsedBar = document.getElementById(this.config.collapsedId);
    
    if (!expandedView || !collapsedBar) return;

    // Animación de salida
    expandedView.style.transition = 'opacity 0.3s ease, max-height 0.5s ease';
    expandedView.style.opacity = '0';
    expandedView.style.maxHeight = '0';
    expandedView.style.overflow = 'hidden';

    setTimeout(() => {
      expandedView.classList.add('hidden');
      
      // Mostrar barra colapsada con animación
      collapsedBar.classList.remove('hidden');
      collapsedBar.style.opacity = '0';
      collapsedBar.style.transform = 'translateY(-10px)';
      
      setTimeout(() => {
        collapsedBar.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        collapsedBar.style.opacity = '1';
        collapsedBar.style.transform = 'translateY(0)';
      }, 50);
    }, 300);

    this.isCollapsed = true;
  },

  /**
   * Expande las alertas de vuelta
   */
  expand() {
    const expandedView = document.getElementById(this.config.expandedId);
    const collapsedBar = document.getElementById(this.config.collapsedId);
    
    if (!expandedView || !collapsedBar) return;

    // Ocultar barra colapsada
    collapsedBar.style.transition = 'opacity 0.2s ease';
    collapsedBar.style.opacity = '0';

    setTimeout(() => {
      collapsedBar.classList.add('hidden');
      
      // Mostrar vista expandida
      expandedView.classList.remove('hidden');
      expandedView.style.opacity = '0';
      expandedView.style.maxHeight = '0';
      
      setTimeout(() => {
        expandedView.style.transition = 'opacity 0.3s ease, max-height 0.5s ease';
        expandedView.style.opacity = '1';
        expandedView.style.maxHeight = '500px';
      }, 50);
    }, 200);

    this.isCollapsed = false;

    // Reiniciar el timer de auto-colapso
    if (this.collapseTimeout) {
      clearTimeout(this.collapseTimeout);
    }
    this.collapseTimeout = setTimeout(() => this.collapse(), this.config.collapseDelay);
  }
};

// Auto-inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  AlertsCollapse.init();
});
