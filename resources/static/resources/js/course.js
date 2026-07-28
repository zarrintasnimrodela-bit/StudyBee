(function () {
    if (window.pdfjsLib) {
        pdfjsLib.GlobalWorkerOptions.workerSrc =
            "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    }

    let currentPdf = null;
    const PDF_SIDE_GAP = 24;
    const PDF_MAX_WIDTHS = {
        landscape: 816,
        portrait: 720,
        balanced: 840
    };
    let currentScale = 1;
    let currentPdfOrientation = "balanced";
    let currentPdfBaseWidth = PDF_MAX_WIDTHS.balanced;
    let currentLoadingTask = null;
    let pdfObserver = null;
    let pdfGeneration = 0;
    const pdfRenderTasks = new Map();
    let pdfResizeTimer = null;

    function getDefaultPdfZoom() {
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
        const previewContent = modal.querySelector(".preview-content");
        const previewTitle = document.getElementById("previewTitle");
        const previewDownload = document.getElementById("previewDownload");
        const previewOpenTab = document.getElementById("previewOpenTab");
        const closeButton = document.getElementById("previewClose");

        if (!modal || !previewBody || !previewTitle || !closeButton) {
            return;
        }

        function resetPdfState() {
            pdfGeneration += 1;
            currentScale = getDefaultPdfZoom();
            currentPdfOrientation = "balanced";
            currentPdfBaseWidth = PDF_MAX_WIDTHS.balanced;

            if (previewContent) {
                previewContent.classList.remove(
                    "pdf-layout-landscape",
                    "pdf-layout-portrait",
                    "pdf-layout-balanced"
                );
            }

            if (pdfObserver) {
                pdfObserver.disconnect();
                pdfObserver = null;
            }

            pdfRenderTasks.forEach((task) => {
                try {
                    task.cancel();
                } catch (error) {
                    // A task may already be complete.
                }
            });
            pdfRenderTasks.clear();

            if (currentLoadingTask && typeof currentLoadingTask.destroy === "function") {
                try {
                    currentLoadingTask.destroy();
                } catch (error) {
                    // Ignore cleanup errors while closing/reopening the modal.
                }
            }
            currentLoadingTask = null;

            if (currentPdf && typeof currentPdf.destroy === "function") {
                try {
                    currentPdf.destroy();
                } catch (error) {
                    // Ignore cleanup errors while closing/reopening the modal.
                }
            }
            currentPdf = null;
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
            const generation = pdfGeneration;

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
                            <strong>Scroll PDF Viewer</strong>
                            <span class="pdf-page-info" id="pdfPageInfo">Loading…</span>
                        </div>
                        <div class="pdf-toolbar-right">
                            <button type="button" class="pdf-tool-btn" id="pdfZoomOut" aria-label="Zoom out">−</button>
                            <span class="pdf-zoom-label" id="pdfZoomLabel">100%</span>
                            <button type="button" class="pdf-tool-btn" id="pdfZoomIn" aria-label="Zoom in">+</button>
                        </div>
                    </div>
                    <div class="pdf-scroll-container" id="pdfScrollContainer" tabindex="0">
                        <div class="pdf-pages-column" id="pdfPagesColumn">
                            <div class="pdf-loading-message">Loading PDF…</div>
                        </div>
                    </div>
                </div>
            `;

            try {
                currentLoadingTask = pdfjsLib.getDocument({
                    url: fileUrl,
                    withCredentials: false
                });
                const loadedPdf = await currentLoadingTask.promise;

                if (generation !== pdfGeneration) {
                    loadedPdf.destroy();
                    return;
                }

                currentPdf = loadedPdf;
                currentLoadingTask = null;

                const firstPage = await currentPdf.getPage(1);
                const firstViewport = firstPage.getViewport({ scale: 1 });
                applyPdfDocumentLayout(firstViewport);
                await waitForPdfLayout();
                refreshPdfBaseWidth();

                await createPdfPageHolders(generation, firstViewport);
                setupPdfObserver(generation);
                renderFirstPdfPages(generation);
            } catch (error) {
                if (generation !== pdfGeneration) {
                    return;
                }

                console.error("PDF loading error:", error);
                showFallback(
                    "PDF loading failed",
                    "The preview could not load this PDF. You can still open or download it.",
                    fileUrl,
                    "Open PDF"
                );
            }
        }

        function getPdfContainer() {
            return document.getElementById("pdfScrollContainer");
        }

        function getPdfOrientation(width, height) {
            const ratio = width / Math.max(1, height);

            if (ratio > 1.12) {
                return "landscape";
            }

            if (ratio < 0.88) {
                return "portrait";
            }

            return "balanced";
        }

        function applyPdfDocumentLayout(viewport) {
            if (!previewContent || !viewport) {
                return;
            }

            const orientation = getPdfOrientation(viewport.width, viewport.height);
            currentPdfOrientation = orientation;

            previewContent.classList.remove(
                "pdf-layout-landscape",
                "pdf-layout-portrait",
                "pdf-layout-balanced"
            );
            previewContent.classList.add(`pdf-layout-${orientation}`);
        }

        function waitForPdfLayout() {
            return new Promise((resolve) => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(resolve);
                });
            });
        }

        function calculatePdfBaseWidth() {
            const container = getPdfContainer();
            const preferredWidth = PDF_MAX_WIDTHS[currentPdfOrientation];

            if (!container) {
                return preferredWidth;
            }

            const availableWidth = Math.max(
                260,
                container.clientWidth - (PDF_SIDE_GAP * 2)
            );

            return Math.max(
                260,
                Math.min(availableWidth, preferredWidth)
            );
        }

        function refreshPdfBaseWidth() {
            currentPdfBaseWidth = calculatePdfBaseWidth();
        }

        function getPdfTargetWidth() {
            return Math.max(260, currentPdfBaseWidth * currentScale);
        }

        function updateZoomLabel() {
            const label = document.getElementById("pdfZoomLabel");
            if (label) {
                label.textContent = `${Math.round(currentScale * 100)}%`;
            }
        }

        function applyPdfPlaceholderSize(holder) {
            const aspect = Number(holder.dataset.aspect) || 1.414;
            const width = getPdfTargetWidth();
            const height = width * aspect;

            holder.style.width = `${Math.round(width)}px`;
            holder.style.height = `${Math.round(height)}px`;
        }

        async function createPdfPageHolders(generation, suppliedFirstViewport = null) {
            if (!currentPdf || generation !== pdfGeneration) {
                return;
            }

            const column = document.getElementById("pdfPagesColumn");
            const info = document.getElementById("pdfPageInfo");

            if (!column) {
                return;
            }

            let firstViewport = suppliedFirstViewport;

            if (!firstViewport) {
                const firstPage = await currentPdf.getPage(1);
                firstViewport = firstPage.getViewport({ scale: 1 });
            }

            const defaultAspect = firstViewport.height / firstViewport.width;

            column.innerHTML = "";

            for (let pageNumber = 1; pageNumber <= currentPdf.numPages; pageNumber += 1) {
                const holder = document.createElement("section");
                holder.className = "pdf-page-holder";
                holder.dataset.page = String(pageNumber);
                holder.dataset.aspect = String(defaultAspect);
                holder.dataset.rendered = "false";
                holder.dataset.rendering = "false";
                holder.setAttribute("aria-label", `PDF page ${pageNumber}`);

                const canvas = document.createElement("canvas");
                canvas.className = "pdf-page-canvas";

                const loading = document.createElement("div");
                loading.className = "pdf-page-loading";
                loading.textContent = `Loading page ${pageNumber}…`;

                holder.appendChild(canvas);
                holder.appendChild(loading);
                applyPdfPlaceholderSize(holder);
                column.appendChild(holder);
            }

            if (info) {
                info.textContent = `${currentPdf.numPages} page${currentPdf.numPages === 1 ? "" : "s"}`;
            }
            updateZoomLabel();
        }

        function setupPdfObserver(generation) {
            if (pdfObserver) {
                pdfObserver.disconnect();
            }

            const container = getPdfContainer();
            if (!container) {
                return;
            }

            pdfObserver = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        renderScrollablePdfPage(entry.target, generation);
                    }
                });
            }, {
                root: container,
                rootMargin: "1000px 0px",
                threshold: 0.01
            });

            document.querySelectorAll(".pdf-page-holder").forEach((holder) => {
                pdfObserver.observe(holder);
            });
        }

        function renderFirstPdfPages(generation) {
            document.querySelectorAll(".pdf-page-holder").forEach((holder, index) => {
                if (index < 2) {
                    renderScrollablePdfPage(holder, generation);
                }
            });
        }

        async function renderScrollablePdfPage(holder, generation) {
            if (!currentPdf || generation !== pdfGeneration || !holder) {
                return;
            }

            if (holder.dataset.rendered === "true" || holder.dataset.rendering === "true") {
                return;
            }

            const pageNumber = Number(holder.dataset.page);
            const canvas = holder.querySelector("canvas");
            const loading = holder.querySelector(".pdf-page-loading");

            if (!pageNumber || !canvas) {
                return;
            }

            holder.dataset.rendering = "true";

            try {
                const page = await currentPdf.getPage(pageNumber);

                if (generation !== pdfGeneration) {
                    return;
                }

                const normalViewport = page.getViewport({ scale: 1 });
                const targetWidth = getPdfTargetWidth();
                const scale = targetWidth / normalViewport.width;
                const viewport = page.getViewport({ scale });
                const outputScale = window.devicePixelRatio || 1;
                const context = canvas.getContext("2d", { alpha: false });

                holder.dataset.aspect = String(viewport.height / viewport.width);
                holder.style.width = `${Math.round(viewport.width)}px`;
                holder.style.height = `${Math.round(viewport.height)}px`;

                canvas.width = Math.floor(viewport.width * outputScale);
                canvas.height = Math.floor(viewport.height * outputScale);
                canvas.style.width = `${Math.floor(viewport.width)}px`;
                canvas.style.height = `${Math.floor(viewport.height)}px`;

                const renderTask = page.render({
                    canvasContext: context,
                    viewport,
                    transform: outputScale !== 1
                        ? [outputScale, 0, 0, outputScale, 0, 0]
                        : null
                });

                pdfRenderTasks.set(pageNumber, renderTask);
                await renderTask.promise;

                if (generation !== pdfGeneration) {
                    return;
                }

                holder.dataset.rendered = "true";
                canvas.classList.add("is-rendered");
                if (loading) {
                    loading.remove();
                }
            } catch (error) {
                if (error && error.name !== "RenderingCancelledException") {
                    console.error(`PDF page ${pageNumber} render error:`, error);
                    if (loading) {
                        loading.textContent = `Page ${pageNumber} could not be rendered.`;
                    }
                }
            } finally {
                holder.dataset.rendering = "false";
                pdfRenderTasks.delete(pageNumber);
            }
        }

        function rerenderScrollablePdf() {
            if (!currentPdf) {
                return;
            }

            const generation = pdfGeneration;
            const container = getPdfContainer();
            const oldScrollableHeight = container
                ? Math.max(1, container.scrollHeight - container.clientHeight)
                : 1;
            const oldScrollRatio = container ? container.scrollTop / oldScrollableHeight : 0;

            pdfRenderTasks.forEach((task) => {
                try {
                    task.cancel();
                } catch (error) {
                    // Ignore already-completed render tasks.
                }
            });
            pdfRenderTasks.clear();

            document.querySelectorAll(".pdf-page-holder").forEach((holder) => {
                const canvas = holder.querySelector("canvas");
                const oldLoading = holder.querySelector(".pdf-page-loading");

                holder.dataset.rendered = "false";
                holder.dataset.rendering = "false";
                applyPdfPlaceholderSize(holder);

                if (canvas) {
                    canvas.width = 1;
                    canvas.height = 1;
                    canvas.style.width = "1px";
                    canvas.style.height = "1px";
                    canvas.classList.remove("is-rendered");
                }

                if (!oldLoading) {
                    const loading = document.createElement("div");
                    loading.className = "pdf-page-loading";
                    loading.textContent = `Loading page ${holder.dataset.page}…`;
                    holder.appendChild(loading);
                }
            });

            updateZoomLabel();
            setupPdfObserver(generation);
            renderFirstPdfPages(generation);

            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    if (container) {
                        const newScrollableHeight = Math.max(1, container.scrollHeight - container.clientHeight);
                        container.scrollTop = oldScrollRatio * newScrollableHeight;
                    }
                });
            });
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

               const folderMatch = parsedUrl.pathname.match(/\/drive\/folders\/([^/?#]+)/);

if (folderMatch && folderMatch[1]) {
    const folderId = folderMatch[1];
    return {
        type: "folder",
        previewUrl: `https://drive.google.com/embeddedfolderview?id=${folderMatch[1]}#list`
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
    previewBody.innerHTML = `
        <div class="preview-folder-wrap">
            <p class="preview-access-note">
                This Google Drive folder may require BRACU GSuite access. If the preview does not load properly, use Open Original.
            </p>

            <iframe
                class="preview-frame drive-folder-frame"
                src="${drivePreviewUrl.previewUrl}">
            </iframe>
        </div>
    `;
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

            if (event.target.id === "pdfZoomIn") {
                currentScale = Math.min(2.5, Number((currentScale + 0.15).toFixed(2)));
                rerenderScrollablePdf();
            }

            if (event.target.id === "pdfZoomOut") {
                currentScale = Math.max(0.5, Number((currentScale - 0.15).toFixed(2)));
                rerenderScrollablePdf();
            }
        });

        window.addEventListener("resize", function () {
            if (!currentPdf) {
                return;
            }

            clearTimeout(pdfResizeTimer);
            pdfResizeTimer = setTimeout(function () {
                refreshPdfBaseWidth();
                rerenderScrollablePdf();
            }, 180);
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

    document.addEventListener("click", handleFilterClick);
    window.addEventListener("popstate", handleBackForward);

    animateResourceCards();
    setupPreviewModal();
    setupCopyResourceLinks();
})();