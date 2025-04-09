// static/js/scripts.js
document.addEventListener('DOMContentLoaded', function() {
  // Preview de imagem no formulário
  const fileInput = document.querySelector('input[type="file"]');
  const imagePreview = document.createElement('img');
  imagePreview.className = 'upload-preview';
  
  if(fileInput) {
    fileInput.parentNode.appendChild(imagePreview);
    
    fileInput.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if(file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
          imagePreview.style.display = 'block';
          imagePreview.src = e.target.result;
        }
        
        reader.readAsDataURL(file);
      }
    });
  }

  // Auto-fechar alerts após 5 segundos
  setTimeout(() => {
    document.querySelectorAll('.alert').forEach(alert => {
      alert.classList.add('fade');
      setTimeout(() => alert.remove(), 300);
    });
  }, 5000);

  // Tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

  // Validação de telefone em tempo real
  const phoneInput = document.querySelector('input[name="telefone"]');
  if(phoneInput) {
    phoneInput.addEventListener('input', function(e) {
      const value = e.target.value.replace(/\D/g,'');
      const formatted = value.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
      e.target.value = formatted;
    });
  }
});

// Função para admin panel
function toggleResponse(id) {
  const element = document.getElementById(`resp${id}`);
  element.classList.toggle('show');
}