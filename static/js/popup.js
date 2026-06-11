function toggleMenu() {

    const menu = document.getElementById("userMenu");

    menu.classList.toggle("hidden");

}

// Tutup dropdown jika klik di luar
document.addEventListener("click", function(event) {

    const menu = document.getElementById("userMenu");
    const button = document.getElementById("userDropdownButton");

    if (!menu || !button) return;

    // Jika menu sedang tampil
    if (!menu.classList.contains("hidden")) {

        if (
            !menu.contains(event.target) &&
            !button.contains(event.target)
        ) {

            menu.classList.add("hidden");

        }

    }

});

function openLogoutModal() {

    document
        .getElementById("userMenu")
        .classList.add("hidden");

    const modal = document.getElementById("logoutModal");

    modal.classList.remove("hidden");
    modal.classList.add("flex");

}

function closeLogoutModal() {

    const modal = document.getElementById("logoutModal");

    modal.classList.remove("flex");
    modal.classList.add("hidden");

}

function confirmLogout() {

    closeLogoutModal();

    const successModal =
        document.getElementById("logoutSuccessModal");

    successModal.classList.remove("hidden");
    successModal.classList.add("flex");

    setTimeout(() => {

        window.location.href = "/login";

    }, 2000);

}