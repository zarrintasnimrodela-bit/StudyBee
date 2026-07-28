const FAVORITES_KEY = "studybee_favorite_courses";
const RECENT_KEY = "studybee_recent_courses";
const MAX_RECENT_COURSES = 6;


function readStoredCourses(key) {
    try {
        const value = JSON.parse(
            localStorage.getItem(key) || "[]"
        );

        return Array.isArray(value) ? value : [];
    } catch (error) {
        return [];
    }
}


function writeStoredCourses(key, courses) {
    try {
        localStorage.setItem(
            key,
            JSON.stringify(courses)
        );
    } catch (error) {
        // Browser storage may be disabled. The page still works.
    }
}


function courseFromCard(card) {
    return {
        id: String(card.dataset.courseId || ""),
        code: card.dataset.courseCode || "",
        title: card.dataset.courseTitle || "",
        url: card.dataset.courseUrl || "",
    };
}


function isFavorite(courseId) {
    return readStoredCourses(FAVORITES_KEY).some(
        (course) => String(course.id) === String(courseId)
    );
}


function setFavorite(course, shouldFavorite) {
    const favorites = readStoredCourses(FAVORITES_KEY).filter(
        (item) => String(item.id) !== String(course.id)
    );

    if (shouldFavorite) {
        favorites.unshift(course);
    }

    writeStoredCourses(FAVORITES_KEY, favorites);
}


function rememberRecent(course) {
    if (!course.id || !course.url) {
        return;
    }

    const recent = readStoredCourses(RECENT_KEY).filter(
        (item) => String(item.id) !== String(course.id)
    );

    recent.unshift(course);

    writeStoredCourses(
        RECENT_KEY,
        recent.slice(0, MAX_RECENT_COURSES)
    );
}


function updateFavoriteButton(button, courseId) {
    const active = isFavorite(courseId);

    button.classList.toggle("active", active);
    button.textContent = active ? "★" : "☆";
    button.setAttribute(
        "aria-label",
        active
            ? "Remove course from favorites"
            : "Add course to favorites"
    );
}


function createPersonalCourseCard(course, showFavoriteButton) {
    const card = document.createElement("div");
    card.className = "personal-course-card";

    const link = document.createElement("a");
    link.href = course.url;
    link.className = "personal-course-link";

    const code = document.createElement("strong");
    code.textContent = course.code;

    const title = document.createElement("span");
    title.textContent = course.title;

    link.append(code, title);
    link.addEventListener("click", function () {
        rememberRecent(course);
    });

    card.appendChild(link);

    if (showFavoriteButton) {
        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "personal-favorite-remove";
        removeButton.textContent = "×";
        removeButton.title = "Remove favorite";

        removeButton.addEventListener("click", function () {
            setFavorite(course, false);
            syncFavoriteButtons();
            renderPersonalSections();
        });

        card.appendChild(removeButton);
    }

    return card;
}


function renderCourseSection(sectionId, gridId, courses, removable) {
    const section = document.getElementById(sectionId);
    const grid = document.getElementById(gridId);

    if (!section || !grid) {
        return;
    }

    grid.replaceChildren();

    courses.forEach(function (course) {
        grid.appendChild(
            createPersonalCourseCard(course, removable)
        );
    });

    section.hidden = courses.length === 0;
}


function renderPersonalSections() {
    renderCourseSection(
        "favoriteCoursesSection",
        "favoriteCoursesGrid",
        readStoredCourses(FAVORITES_KEY),
        true
    );

    renderCourseSection(
        "recentCoursesSection",
        "recentCoursesGrid",
        readStoredCourses(RECENT_KEY),
        false
    );
}


function syncFavoriteButtons() {
    document.querySelectorAll(".course-card").forEach(
        function (card) {
            const button = card.querySelector(
                ".favorite-course-btn"
            );

            if (button) {
                updateFavoriteButton(
                    button,
                    card.dataset.courseId
                );
            }
        }
    );
}


const revealElements = document.querySelectorAll(".reveal");

if (revealElements.length) {
    const revealObserver = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("show");
                }
            });
        },
        {threshold: 0.12}
    );

    revealElements.forEach(function (element) {
        revealObserver.observe(element);
    });
}


document.addEventListener("click", function (event) {
    const favoriteButton = event.target.closest(
        ".favorite-course-btn"
    );

    if (favoriteButton) {
        const card = favoriteButton.closest(".course-card");

        if (!card) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        const course = courseFromCard(card);
        const nextState = !isFavorite(course.id);

        setFavorite(course, nextState);
        updateFavoriteButton(
            favoriteButton,
            course.id
        );
        renderPersonalSections();
        return;
    }

    const courseLink = event.target.closest(
        ".course-card-link"
    );

    if (!courseLink) {
        return;
    }

    const card = courseLink.closest(".course-card");
    const url = courseLink.getAttribute("href");

    if (!card || !url) {
        return;
    }

    rememberRecent(courseFromCard(card));
    event.preventDefault();

    card.classList.add("course-card-clicked");
    document.body.classList.add("page-exit");

    setTimeout(function () {
        window.location.href = url;
    }, 220);
});


// Live course filtering. Normal form submission remains available.
(function () {
    const searchInput = document.getElementById(
        "courseSearchInput"
    );
    const courseCards = document.querySelectorAll(
        ".course-card"
    );
    const courseGrid = document.querySelector(
        ".course-grid"
    );

    if (
        !searchInput
        || !courseCards.length
        || !courseGrid
    ) {
        return;
    }

    let emptyMessage = document.querySelector(
        ".live-search-empty"
    );

    if (!emptyMessage) {
        emptyMessage = document.createElement("div");
        emptyMessage.className = "live-search-empty";

        const icon = document.createElement("div");
        icon.className = "empty-icon";
        icon.textContent = "🍯";

        const heading = document.createElement("h3");
        heading.textContent = "No courses found";

        const paragraph = document.createElement("p");
        paragraph.textContent = (
            "Press Search all to search resource titles too."
        );

        emptyMessage.append(icon, heading, paragraph);
        emptyMessage.style.display = "none";
        courseGrid.after(emptyMessage);
    }

    function showCardWithAnimation(card, index) {
        card.style.display = "";
        card.classList.remove("show");

        setTimeout(function () {
            card.classList.add("show");
        }, index * 70);
    }

    function filterCourses() {
        const searchText = searchInput.value
            .trim()
            .toLowerCase();
        let visibleCount = 0;

        courseCards.forEach(function (card) {
            const cardText = card.textContent.toLowerCase();

            if (cardText.includes(searchText)) {
                showCardWithAnimation(
                    card,
                    visibleCount
                );
                visibleCount += 1;
            } else {
                card.classList.remove("show");
                card.style.display = "none";
            }
        });

        emptyMessage.style.display = (
            visibleCount === 0
                ? "block"
                : "none"
        );
    }

    searchInput.addEventListener(
        "input",
        filterCourses
    );

    if (searchInput.value.trim()) {
        filterCourses();
    }
})();


// About modal.
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

    aboutModal.addEventListener(
        "click",
        function (event) {
            if (event.target === aboutModal) {
                closeAbout();
            }
        }
    );

    document.addEventListener(
        "keydown",
        function (event) {
            if (
                event.key === "Escape"
                && aboutModal.classList.contains("show")
            ) {
                closeAbout();
            }
        }
    );
})();


syncFavoriteButtons();
renderPersonalSections();
