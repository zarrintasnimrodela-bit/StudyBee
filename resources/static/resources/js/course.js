(function () {
    if (window.pdfjsLib) {
        pdfjsLib.GlobalWorkerOptions.workerSrc =
            "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.6.347/pdf.worker.min.js";
    }

let currentPdf = null;
let currentPage = 1;
let currentScale = getDefaultPdfZoom();
let currentRenderTask = null;

function getDefaultPdfZoom() {
    if (window.innerWidth <= 700) {
        return 1.2;
    }

    return 1;
}



    function animateResourceCards() {
        const cards = document.querySelectorAll(".resource-card.reveal");

        cards.forEach((card, index) => {
            card.classList.remove("show");

            setTimeout(() => {
                card.classList.add("show");
            }, index * 70);
        });
    }

    function replacePageParts(htmlText) {
        const parser = new DOMParser();
        const newDocument = parser.parseFromString(htmlText, "text/html");

        const newFilterPanel = newDocument.querySelector(".filter-panel");
        const newResourceSection = newDocument.querySelector(".resource-section");

        const currentFilterPanel = document.querySelector(".filter-panel");
        const currentResourceSection = document.querySelector(".resource-section");

        if (newFilterPanel && currentFilterPanel) {
            currentFilterPanel.innerHTML = newFilterPanel.innerHTML;
        }

        if (newResourceSection && currentResourceSection) {
            currentResourceSection.classList.add("is-changing");

            setTimeout(() => {
                currentResourceSection.innerHTML = newResourceSection.innerHTML;
                currentResourceSection.classList.remove("is-changing");
                animateResourceCards();
            }, 160);
        }
    }

    async function handleFilterClick(event) {
        const link = event.target.closest(".filter-chip");

        if (!link) {
            return;
        }

        event.preventDefault();

        const url = link.getAttribute("href");

        if (!url) {
            return;
        }

        try {
            const response = await fetch(url, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!response.ok) {
                window.location.href = url;
                return;
            }

            const htmlText = await response.text();

            replacePageParts(htmlText);
            window.history.pushState({}, "", url);

        } catch (error) {
            window.location.href = url;
        }
    }

    async function handleBackForward() {
        try {
            const response = await fetch(window.location.href, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            if (!response.ok) {
                window.location.reload();
                return;
            }

            const htmlText = await response.text();
            replacePageParts(htmlText);

        } catch (error) {
            window.location.reload();
        }
    }

    function setupPreviewModal() {
        const modal = document.getElementById("previewModal");
        const previewBody = document.getElementById("previewBody");
        const previewTitle = document.getElementById("previewTitle");
        const previewDownload = document.getElementById("previewDownload");
        const previewOpenTab = document.getElementById("previewOpenTab");
        const closeButton = document.getElementById("previewClose");

        if (!modal || !previewBody || !previewTitle || !closeButton) {
            return;
        }

        function resetPdfState() {
            currentPdf = null;
            currentPage = 1;
            currentScale = getDefaultPdfZoom();

            if (currentRenderTask) {
                currentRenderTask.cancel();
                currentRenderTask = null;
            }
        }

        function openPreviewShell(title) {
            previewTitle.textContent = title || "Preview";
            modal.classList.add("show");
            document.body.style.overflow = "hidden";
        }

        function showHeaderDownload(url, label, shouldDownload) {
            if (!previewDownload) {
                return;
            }

            previewDownload.href = url;
            previewDownload.textContent = label;

            if (shouldDownload) {
                previewDownload.setAttribute("download", "");
                previewDownload.removeAttribute("target");
            } else {
                previewDownload.removeAttribute("download");
                previewDownload.setAttribute("target", "_blank");
            }

            previewDownload.style.display = "inline-block";
        }

        function hideHeaderDownload() {
            if (!previewDownload) {
                return;
            }

            previewDownload.href = "#";
            previewDownload.textContent = "Download";
            previewDownload.style.display = "none";
            previewDownload.removeAttribute("target");
            previewDownload.setAttribute("download", "");
        }

        function showOpenTab(url) {
            if (!previewOpenTab) {
                return;
            }

            previewOpenTab.href = url;
            previewOpenTab.style.display = "inline-block";
        }

        function hideOpenTab() {
            if (!previewOpenTab) {
                return;
            }

            previewOpenTab.href = "#";
            previewOpenTab.style.display = "none";
        }

        function isImageUrl(url) {
            const lowerUrl = url.toLowerCase();

            return lowerUrl.endsWith(".jpg") ||
                lowerUrl.endsWith(".jpeg") ||
                lowerUrl.endsWith(".png") ||
                lowerUrl.endsWith(".gif") ||
                lowerUrl.endsWith(".webp");
        }

        function isPdfUrl(url) {
            return url.toLowerCase().endsWith(".pdf");
        }

        function isGoogleResource(url) {
            const lowerUrl = url.toLowerCase();

            return lowerUrl.includes("drive.google.com") ||
                lowerUrl.includes("docs.google.com") ||
                lowerUrl.includes("sheets.google.com") ||
                lowerUrl.includes("slides.google.com");
        }

        function getGoogleAccessNote(url) {
            if (!isGoogleResource(url)) {
                return "";
            }

            return `
                <p class="preview-access-note">
                    This Google Drive or document link may require you to sign in with your BRACU GSuite account.
                </p>
            `;
        }

        function showFallback(title, message, linkUrl, linkLabel, extraNote = "") {
            resetPdfState();

            previewBody.innerHTML = `
                <div class="preview-fallback">
                    <h3>${title}</h3>
                    <p>${message}</p>
                    ${extraNote}
                    <a href="${linkUrl}" target="_blank" class="btn link-btn preview-original-link">
                        ${linkLabel}
                    </a>
                </div>
            `;
        }

        function openModal(fileUrl, fileTitle) {
            const safeFileUrl = encodeURI(fileUrl);

            openPreviewShell(fileTitle || "File Preview");

            showOpenTab(safeFileUrl);
            showHeaderDownload(safeFileUrl, "Download", true);

            if (isImageUrl(safeFileUrl)) {
                resetPdfState();

                previewBody.innerHTML = `
                    <img src="${safeFileUrl}" alt="${fileTitle || "File Preview"}">
                `;
            } else if (isPdfUrl(safeFileUrl)) {
                loadPdfPreview(safeFileUrl);
            } else {
                showFallback(
                    "Preview not available",
                    "This file type cannot be previewed in the browser.",
                    safeFileUrl,
                    "Open file"
                );
            }
        }

        async function loadPdfPreview(fileUrl) {
            resetPdfState();

            if (!window.pdfjsLib) {
                showFallback(
                    "PDF.js not loaded",
                    "Please check your internet connection or CDN script.",
                    fileUrl,
                    "Open PDF"
                );
                return;
            }

            previewBody.innerHTML = `
                <div class="pdf-viewer">
                    <div class="pdf-toolbar">
                        <div class="pdf-toolbar-left">
                            <button type="button" class="pdf-tool-btn" id="pdfPrev">← Prev</button>
                            <span class="pdf-page-info">
                                Page <span id="pdfCurrentPage">1</span> / <span id="pdfTotalPages">?</span>
                            </span>
                            <button type="button" class="pdf-tool-btn" id="pdfNext">Next →</button>
                        </div>

                        <div class="pdf-toolbar-right">
                            <button type="button" class="pdf-tool-btn" id="pdfZoomOut">−</button>
                            <button type="button" class="pdf-tool-btn" id="pdfZoomIn">+</button>
                        </div>
                    </div>

                    <div class="pdf-canvas-wrap">
                        <canvas id="pdfCanvas"></canvas>
                    </div>
                </div>
            `;

            try {
                const loadingTask = pdfjsLib.getDocument(fileUrl);
                currentPdf = await loadingTask.promise;

                const totalPagesLabel = document.getElementById("pdfTotalPages");

                if (totalPagesLabel) {
                    totalPagesLabel.textContent = currentPdf.numPages;
                }

                await renderPdfPage(1);

            } catch (error) {
                showFallback(
                    "PDF loading failed",
                    "PDF.js could not load this PDF. Please open it directly.",
                    fileUrl,
                    "Open PDF"
                );
            }
        }

function getResponsivePdfScale(page) {
    const canvasWrap = document.querySelector(".pdf-canvas-wrap");
    const normalViewport = page.getViewport({ scale: 1 });

    if (!canvasWrap) {
        return currentScale;
    }

    if (window.innerWidth <= 700) {
        const availableWidth = canvasWrap.clientWidth - 24;
        const fitScale = availableWidth / normalViewport.width;

        return fitScale * currentScale;
    }

    if (window.innerWidth <= 1000) {
        const availableWidth = canvasWrap.clientWidth - 36;
        const fitScale = availableWidth / normalViewport.width;

        return fitScale * currentScale;
    }

    return 1.35 * currentScale;
}

        async function renderPdfPage(pageNumber) {
            if (!currentPdf) {
                return;
            }

            if (currentRenderTask) {
                currentRenderTask.cancel();
                currentRenderTask = null;
            }

            currentPage = pageNumber;

            const canvas = document.getElementById("pdfCanvas");
            const currentPageLabel = document.getElementById("pdfCurrentPage");

            if (!canvas || !currentPageLabel) {
                return;
            }

            currentPageLabel.textContent = currentPage;

            try {
                const page = await currentPdf.getPage(currentPage);
                const viewport = page.getViewport({ scale: getResponsivePdfScale(page) });

                const outputScale = window.devicePixelRatio || 1;
                const context = canvas.getContext("2d");

                canvas.width = Math.floor(viewport.width * outputScale);
                canvas.height = Math.floor(viewport.height * outputScale);

                canvas.style.width = Math.floor(viewport.width) + "px";
                canvas.style.height = Math.floor(viewport.height) + "px";

                const transform = outputScale !== 1
                    ? [outputScale, 0, 0, outputScale, 0, 0]
                    : null;

                currentRenderTask = page.render({
                    canvasContext: context,
                    viewport: viewport,
                    transform: transform
                });

                await currentRenderTask.promise;
                currentRenderTask = null;

            } catch (error) {
                if (error && error.name === "RenderingCancelledException") {
                    return;
                }

                console.log("PDF render error:", error);
            }
        }

        function closeModal() {
            modal.classList.remove("show");
            previewBody.innerHTML = "";
            document.body.style.overflow = "";
            hideOpenTab();
            hideHeaderDownload();
            resetPdfState();
        }

        function getYouTubeEmbedUrl(url) {
        try {
            const parsedUrl = new URL(url);
            const hostname = parsedUrl.hostname;

            if (hostname.includes("youtube.com")) {
                const videoId = parsedUrl.searchParams.get("v");

                if (videoId) {
                    return `https://www.youtube.com/embed/${videoId}`;
                }

                if (parsedUrl.pathname.startsWith("/shorts/")) {
                    const shortsId = parsedUrl.pathname.split("/shorts/")[1];

                    if (shortsId) {
                        return `https://www.youtube.com/embed/${shortsId}`;
                    }
                }
            }

            if (hostname.includes("youtu.be")) {
                const videoId = parsedUrl.pathname.replace("/", "");

                if (videoId) {
                    return `https://www.youtube.com/embed/${videoId}`;
                }
            }

            return null;
        } catch (error) {
            return null;
        }
    }

        function getGoogleDrivePreviewUrl(url) {
            try {
                const parsedUrl = new URL(url);
                const hostname = parsedUrl.hostname;

                if (hostname.includes("docs.google.com")) {
                    const docMatch = parsedUrl.pathname.match(/\/(document|spreadsheets|presentation)\/d\/([^/]+)/);

                    if (docMatch && docMatch[1] && docMatch[2]) {
                        const docType = docMatch[1];
                        const docId = docMatch[2];

                        return {
                            type: "google_doc",
                            previewUrl: `https://docs.google.com/${docType}/d/${docId}/preview`
                        };
                    }

                    return {
                        type: "unknown",
                        previewUrl: url
                    };
                }

                if (!hostname.includes("drive.google.com")) {
                    return null;
                }

                const fileMatch = parsedUrl.pathname.match(/\/file\/d\/([^/]+)/);

                if (fileMatch && fileMatch[1]) {
                    return {
                        type: "file",
                        previewUrl: `https://drive.google.com/file/d/${fileMatch[1]}/preview`
                    };
                }

                if (parsedUrl.pathname.includes("/open")) {
                    const fileId = parsedUrl.searchParams.get("id");

                    if (fileId) {
                        return {
                            type: "file",
                            previewUrl: `https://drive.google.com/file/d/${fileId}/preview`
                        };
                    }
                }

                const folderMatch = parsedUrl.pathname.match(/\/drive\/folders\/([^/]+)/);

                if (folderMatch && folderMatch[1]) {
                    return {
                        type: "folder",
                        previewUrl: url
                    };
                }

                return {
                    type: "unknown",
                    previewUrl: url
                };

            } catch (error) {
                return null;
            }
        }

        function openExternalPreview(url, title) {
            const safeUrl = encodeURI(url);

            openPreviewShell(title || "Link Preview");

            hideOpenTab();
            showHeaderDownload(safeUrl, "Open Original", false);

            const youtubeEmbedUrl = getYouTubeEmbedUrl(url);
            const drivePreviewUrl = getGoogleDrivePreviewUrl(url);
            const googleAccessNote = getGoogleAccessNote(url);

            if (youtubeEmbedUrl) {
                resetPdfState();

                const youtubeUrlWithOptions =
                    `${youtubeEmbedUrl}?rel=0&modestbranding=1&origin=${encodeURIComponent(window.location.origin)}`;

                previewBody.innerHTML = `
                    <div class="preview-video-wrap">
                        <iframe
                            src="${youtubeUrlWithOptions}"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                            referrerpolicy="strict-origin-when-cross-origin"
                            allowfullscreen>
                        </iframe>
                    </div>
                `;
            } else if (drivePreviewUrl) {
                resetPdfState();

                if (drivePreviewUrl.type === "file" || drivePreviewUrl.type === "google_doc") {
                    previewBody.innerHTML = `
                        <iframe class="preview-frame" src="${drivePreviewUrl.previewUrl}" allow="autoplay"></iframe>
                    `;
                } else if (drivePreviewUrl.type === "folder") {
                    showFallback(
                        "Drive folder preview",
                        "Google Drive folders cannot always be previewed inside StudyBee. Please open it directly.",
                        safeUrl,
                        "Open Drive Folder",
                        googleAccessNote
                    );
                } else {
                    showFallback(
                        "Preview may not be available",
                        "This Google link may not allow opening inside StudyBee.",
                        safeUrl,
                        "Open original link",
                        googleAccessNote
                    );
                }
            } else if (isImageUrl(safeUrl)) {
                resetPdfState();

                previewBody.innerHTML = `
                    <img src="${safeUrl}" alt="${title || "Image Preview"}">
                `;
            } else if (isPdfUrl(safeUrl)) {
                showOpenTab(safeUrl);
                showHeaderDownload(safeUrl, "Download", true);
                loadPdfPreview(safeUrl);
            } else {
                showFallback(
                    "Preview may not be available",
                    "This link may not allow opening inside StudyBee.",
                    safeUrl,
                    "Open original link"
                );
            }
        }

        document.addEventListener("click", function (event) {
            const previewButton = event.target.closest(".preview-btn");

            if (!previewButton) {
                return;
            }

            const fileUrl = previewButton.dataset.fileUrl;
            const fileTitle = previewButton.dataset.fileTitle || "File Preview";

            if (!fileUrl) {
                return;
            }

            openModal(fileUrl, fileTitle);
        });

        document.addEventListener("click", function (event) {
            const externalButton = event.target.closest(".external-preview-btn");

            if (!externalButton) {
                return;
            }

            const externalUrl = externalButton.dataset.externalUrl;
            const externalTitle = externalButton.dataset.externalTitle || "Link Preview";

            if (!externalUrl) {
                return;
            }

            openExternalPreview(externalUrl, externalTitle);
        });

        previewBody.addEventListener("click", function (event) {
            if (!currentPdf) {
                return;
            }

            if (event.target.id === "pdfPrev") {
                if (currentPage > 1) {
                    renderPdfPage(currentPage - 1);
                }
            }

            if (event.target.id === "pdfNext") {
                if (currentPage < currentPdf.numPages) {
                    renderPdfPage(currentPage + 1);
                }
            }

            if (event.target.id === "pdfZoomIn") {
                currentScale += 0.15;
                renderPdfPage(currentPage);
            }

            if (event.target.id === "pdfZoomOut") {
                if (currentScale > 0.55) {
                    currentScale -= 0.15;
                    renderPdfPage(currentPage);
                }
            }
        });

        closeButton.addEventListener("click", closeModal);

        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                closeModal();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && modal.classList.contains("show")) {
                closeModal();
            }
        });
    }

    document.addEventListener("click", handleFilterClick);
    window.addEventListener("popstate", handleBackForward);

    animateResourceCards();
    setupPreviewModal();
})();


function setupCopyResourceLinks() {
    document.addEventListener("click", async function (event) {
        const copyButton = event.target.closest(".copy-link-btn");

        if (!copyButton) {
            return;
        }

        const url = copyButton.getAttribute("data-copy-url");

        if (!url) {
            return;
        }

        try {
            await navigator.clipboard.writeText(url);

            const oldText = copyButton.textContent;
            copyButton.textContent = "✓";
            copyButton.classList.add("copied");

            setTimeout(function () {
                copyButton.textContent = oldText;
                copyButton.classList.remove("copied");
            }, 1200);

        } catch (error) {
            window.prompt("Copy this link:", url);
        }
    });
}

setupCopyResourceLinks();