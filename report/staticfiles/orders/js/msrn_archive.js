// JS spécifique pour la page d'archive MSRN
(function() {
  'use strict';
  document.addEventListener('DOMContentLoaded', function() {
    // Amélioration UX: focus automatique sur la recherche si vide
    var q = document.getElementById('q');
    if (q && !q.value) {
      q.focus();
    }

    // Fonction pour récupérer le cookie CSRF
    function getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      return cookieValue;
    }

    // Initialiser les tooltips Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Attacher le gestionnaire aux boutons de téléchargement
    var downloadButtons = document.querySelectorAll('.download-msrn[data-report-id]');
    downloadButtons.forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        var reportId = this.getAttribute('data-report-id');
        
        // Téléchargement direct du rapport MSRN depuis la base de données
        window.location.href = '/orders/msrn-report/' + reportId + '/';
      });
    });

    // Références aux éléments du modal de rétention personnalisé
    const retentionModal = document.getElementById('retentionModal');
    const retentionForm = document.getElementById('retentionForm');
    const msrnIdInput = document.getElementById('msrn-id');
    const msrnNumberSpan = document.getElementById('msrn-number');
    const retentionRateInput = document.getElementById('retention-rate');
    const retentionCauseInput = document.getElementById('retention-cause');
    const causeRequiredMessage = document.getElementById('cause-required-message');
    const saveRetentionBtn = document.getElementById('save-retention');
    const closeModalBtn = document.getElementById('close-modal');
    const cancelModalBtn = document.getElementById('cancel-modal');
    const modalOverlay = document.querySelector('.custom-modal-overlay');

    // Fonctions pour ouvrir et fermer le modal personnalisé
    function openModal() {
      retentionModal.classList.add('show');
      document.body.style.overflow = 'hidden'; // Empêcher le défilement du body
      setTimeout(() => {
        retentionModal.querySelector('.custom-modal-container').style.transform = 'translateY(0)';
        retentionModal.querySelector('.custom-modal-container').style.opacity = '1';
      }, 10);
    }

    function closeModal() {
      const modalContainer = retentionModal.querySelector('.custom-modal-container');
      modalContainer.style.transform = 'translateY(-50px)';
      modalContainer.style.opacity = '0';
      
      setTimeout(() => {
        retentionModal.classList.remove('show');
        document.body.style.overflow = ''; // Rétablir le défilement du body
      }, 300); // Attendre la fin de l'animation
    }

    // Attacher les gestionnaires d'événements pour fermer le modal
    closeModalBtn.addEventListener('click', closeModal);
    cancelModalBtn.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', closeModal);

    // Attacher le gestionnaire aux boutons "Définir la rétention"
    const setRetentionButtons = document.querySelectorAll('.set-retention-btn');
    setRetentionButtons.forEach(function(btn) {
      btn.addEventListener('click', function() {
        const reportId = this.getAttribute('data-report-id');
        const reportNumber = this.getAttribute('data-report-number');
        const retentionRate = this.getAttribute('data-retention-rate') || '0';
        const retentionCause = this.getAttribute('data-retention-cause') || '';
        
        // Remplir le modal avec les valeurs actuelles
        msrnIdInput.value = reportId;
        msrnNumberSpan.textContent = reportNumber;
        retentionRateInput.value = retentionRate;
        retentionCauseInput.value = retentionCause;
        
        // Afficher ou masquer le message d'erreur selon le taux
        updateCauseRequiredMessage();
        
        // Ouvrir le modal personnalisé
        openModal();
      });
    });

    // Fonction pour valider le formulaire
    function validateRetentionForm() {
      const rate = parseFloat(retentionRateInput.value);
      const cause = retentionCauseInput.value.trim();
      
      // Vérifier que le taux est entre 0 et 100 - MODIFIÉ: avant limite 10%
      if (isNaN(rate) || rate < 0 || rate > 100) {
        Swal.fire({
          icon: 'error',
          title: 'Invalid retention rate',
          text: 'The retention rate must be between 0 and 100%',  // MODIFIÉ: message avant "0 and 10%"
          confirmButtonColor: '#3085d6'
        });
        return false;
      }
      
      // Vérifier que la cause est renseignée si le taux > 0
      if (rate > 0 && !cause) {
        causeRequiredMessage.classList.remove('d-none');
        retentionCauseInput.focus();
        return false;
      }
      
      return true;
    }

    // Fonction pour mettre à jour le message d'erreur de cause requise
    function updateCauseRequiredMessage() {
      const rate = parseFloat(retentionRateInput.value);
      if (rate > 0 && !retentionCauseInput.value.trim()) {
        causeRequiredMessage.classList.remove('d-none');
      } else {
        causeRequiredMessage.classList.add('d-none');
      }
    }

    // Écouter les changements sur le taux de rétention
    retentionRateInput.addEventListener('input', updateCauseRequiredMessage);
    retentionRateInput.addEventListener('change', updateCauseRequiredMessage);

    // Écouter les changements sur la cause de rétention
    retentionCauseInput.addEventListener('input', updateCauseRequiredMessage);

    // Gérer la soumission du formulaire
    saveRetentionBtn.addEventListener('click', async function() {
      if (!validateRetentionForm()) {
        return;
      }
      
      const msrnId = msrnIdInput.value;
      const retentionRate = retentionRateInput.value;
      const retentionCause = retentionCauseInput.value.trim();
      
      // Afficher un indicateur de chargement
      Swal.fire({
        title: 'Updating...',
        html: 'Please wait while updating the MSRN report.',
        allowOutsideClick: false,
        didOpen: () => {
          Swal.showLoading();
        }
      });
      
      try {
        // Appeler l'API pour mettre à jour la rétention
        const response = await fetch(`/orders/api/msrn/${msrnId}/update-retention/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
          },
          body: JSON.stringify({
            retention_rate: retentionRate,
            retention_cause: retentionCause
          })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
          // Fermer le modal personnalisé
          closeModal();
          
          // Afficher un message de succès
          Swal.fire({
            icon: 'success',
            title: 'Retention updated',
            text: data.message,
            confirmButtonColor: '#3085d6'
          }).then(() => {
            // Recharger la page pour afficher les nouvelles valeurs
            window.location.reload();
          });
        } else {
          // Afficher un message d'erreur
          Swal.fire({
            icon: 'error',
            title: 'Error',
            text: data.error || 'An error occurred while updating the retention.',
            confirmButtonColor: '#3085d6'
          });
        }
      } catch (error) {
        console.error('Erreur lors de la mise à jour de la rétention:', error);
        
        // Afficher un message d'erreur
        Swal.fire({
          icon: 'error',
          title: 'Error',
          text: 'An error occurred while updating the retention.',
          confirmButtonColor: '#3085d6'
        });
      }
    });
  });
})();
