
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('flyer-form');
  const flyerSection = document.getElementById('popular-flyers');

  form.addEventListener('submit', (e) => {
    e.preventDefault();

    const storeName = document.getElementById('storeName').value;
    const flyerUrl = document.getElementById('flyerUrl').value;

    const flyerCard = document.createElement('div');
    flyerCard.classList.add('flyer-card');
    flyerCard.innerHTML = `
      <a href="${flyerUrl}" target="_blank">
        🛒 ${storeName} - Recently added
      </a>
      <iframe src="${flyerUrl}" width="100%" height="400" frameborder="0"></iframe>
    `;

    flyerSection.appendChild(flyerCard);

    form.reset();
  });
});
