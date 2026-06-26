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

function confirmLogout(){

    closePopup("logoutConfirm");

    openPopup("logoutSuccess");

    setTimeout(function(){

        window.location.href="/login";

    },2000);

}

function openPopup(id){
    document.getElementById(id).style.display="flex";
}

function closePopup(id){
    document.getElementById(id).style.display="none";
}