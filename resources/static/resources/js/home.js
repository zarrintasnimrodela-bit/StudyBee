const revealElements = document.querySelectorAll(".reveal");

const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
        if (entry.isIntersecting) {
            entry.target.classList.add("show");
        }
    });
}, {
    threshold: 0.12
});

revealElements.forEach((element) => {
    revealObserver.observe(element);
});

document.addEventListener("click", function (event) {
    const courseLink = event.target.closest(".course-card");

    if (!courseLink) {
        return;
    }

    const url = courseLink.getAttribute("href");

    if (!url) {
        return;
    }

    event.preventDefault();

    courseLink.classList.add("course-card-clicked");
    document.body.classList.add("page-exit");

    setTimeout(function () {
        window.location.href = url;
    }, 260);
});

// Live course search without page refresh + reveal animation
(function () {
    const searchInput = document.getElementById("courseSearchInput");
    const searchForm = searchInput ? searchInput.closest("form") : null;
    const courseCards = document.querySelectorAll(".course-card");
    const courseGrid = document.querySelector(".course-grid");

    if (!searchInput || !courseCards.length || !courseGrid) {
        return;
    }

    let emptyMessage = document.querySelector(".live-search-empty");

    if (!emptyMessage) {
        emptyMessage = document.createElement("div");
        emptyMessage.className = "live-search-empty";
        emptyMessage.innerHTML = `
            <div class="empty-icon">🍯</div>
            <h3>No courses found</h3>
            <p>Try searching with a different course code or title.</p>
        `;
        emptyMessage.style.display = "none";
        courseGrid.after(emptyMessage);
    }

    function showCardWithAnimation(card, index) {
        card.style.display = "";

        card.classList.remove("show");

        setTimeout(function () {
            card.classList.add("show");
        }, index * 85);
    }

    function filterCourses() {
        const searchText = searchInput.value.trim().toLowerCase();
        let visibleCount = 0;

        courseCards.forEach(function (card) {
            const cardText = card.textContent.toLowerCase();

            if (cardText.includes(searchText)) {
                showCardWithAnimation(card, visibleCount);
                visibleCount++;
            } else {
                card.classList.remove("show");
                card.style.display = "none";
            }
        });

        emptyMessage.style.display = visibleCount === 0 ? "block" : "none";
    }

    searchInput.addEventListener("input", filterCourses);

    if (searchForm) {
        searchForm.addEventListener("submit", function (event) {
            event.preventDefault();
            filterCourses();
        });
    }
})();

// About modal
(function () {
    const aboutOpen = document.getElementById("aboutOpen");
    const aboutModal = document.getElementById("aboutModal");
    const aboutClose = document.getElementById("aboutClose");

    if (!aboutOpen || !aboutModal || !aboutClose) {
        return;
    }

    function openAbout() {
        aboutModal.classList.add("show");
        document.body.style.overflow = "hidden";
    }

    function closeAbout() {
        aboutModal.classList.remove("show");
        document.body.style.overflow = "";
    }

    aboutOpen.addEventListener("click", openAbout);
    aboutClose.addEventListener("click", closeAbout);

    aboutModal.addEventListener("click", function (event) {
        if (event.target === aboutModal) {
            closeAbout();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && aboutModal.classList.contains("show")) {
            closeAbout();
        }
    });
})();