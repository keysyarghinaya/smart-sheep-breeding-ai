/* ============================================================
   DombaKu â€“ Popup JavaScript
   ============================================================ */

function openPopup(id) {
  const overlay = document.getElementById(id);
  if (overlay) {
    overlay.classList.add("active");
  }
}

function closePopup(id) {
  const overlay = document.getElementById(id);
  if (overlay) {
    overlay.classList.remove("active");
  }
}

function toggleMenu() {
  const menu = document.getElementById("userMenu");
  if (menu) {
    menu.classList.toggle("hidden");
  }
}

function openLogoutModal() {
  const userMenu = document.getElementById("userMenu")
  if (userMenu) {
    userMenu.classList.add("hidden");
  }
  openPopup("logoutConfirm");
}

function confirmLogout() {
  closePopup("logoutConfirm");
  openPopup("logoutSuccess");
  setTimeout(function () {
    window.location.href = "/logout";
  }, 1500);
}
