(function () {
    if (window.pdfjsLib) {
        pdfjsLib.GlobalWorkerOptions.workerSrc =
            "https://cdn.jsdelivr.net/npm/pdfjs-dist@5.7.284/build/pdf.worker.min.mjs";
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
    let currentImageScale = 1;
    let currentImageBaseWidth = 0;
    let currentImageNaturalWidth = 0;
    let currentImageNaturalHeight = 0;

    function getDefaultPdfZoom() {
        return 1;
    }


    function getSafeHttpUrl(value) {
        try {
            const parsedUrl = new URL(value, window.location.href);

            if (!["http:", "https:"].includes(parsedUrl.protocol)) {
                return null;
            }

            return parsedUrl;
        } catch (error) {
            return null;
        }
    }

    function hostnameMatches(hostname, allowedDomain) {
        const normalizedHost = hostname.toLowerCase().replace(/\.$/, "");
        const normalizedDomain = allowedDomain.toLowerCase();

        return normalizedHost === normalizedDomain ||
            normalizedHost.endsWith(`.${normalizedDomain}`);
    }

    function hasSafeId(value) {
        return /^[A-Za-z0-9_-]+$/.test(value || "");
    }

    function replaceChildrenFromSource(target, source) {
        const importedNodes = Array.from(
            source.childNodes,
            (node) => document.importNode(node, true)
        );

        target.replaceChildren(...importedNodes);
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
            replaceChildrenFromSource(currentFilterPanel, newFilterPanel);
        }

        if (newResourceSection && currentResourceSection) {
            currentResourceSection.classList.add("is-changing");

            setTimeout(() => {
                replaceChildrenFromSource(currentResourceSection, newResourceSection);
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
            currentImageScale = 1;
            currentImageBaseWidth = 0;
            currentImageNaturalWidth = 0;
            currentImageNaturalHeight = 0;

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

            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                hideHeaderDownload();
                return;
            }

            previewDownload.href = parsedUrl.href;
            previewDownload.textContent = label;
            previewDownload.rel = "noopener noreferrer";

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

            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                hideOpenTab();
                return;
            }

            previewOpenTab.href = parsedUrl.href;
            previewOpenTab.rel = "noopener noreferrer";
            previewOpenTab.style.display = "inline-block";
        }

        function hideOpenTab() {
            if (!previewOpenTab) {
                return;
            }

            previewOpenTab.href = "#";
            previewOpenTab.style.display = "none";
        }

        function getUrlPathname(url) {
            const parsedUrl = getSafeHttpUrl(url);
            return parsedUrl ? parsedUrl.pathname.toLowerCase() : "";
        }

        function isImageUrl(url) {
            const pathname = getUrlPathname(url);

            return pathname.endsWith(".jpg") ||
                pathname.endsWith(".jpeg") ||
                pathname.endsWith(".png") ||
                pathname.endsWith(".gif") ||
                pathname.endsWith(".webp");
        }

        function isPdfUrl(url) {
            return getUrlPathname(url).endsWith(".pdf");
        }

        function isGoogleResource(url) {
            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                return false;
            }

            return hostnameMatches(parsedUrl.hostname, "drive.google.com") ||
                hostnameMatches(parsedUrl.hostname, "docs.google.com") ||
                hostnameMatches(parsedUrl.hostname, "sheets.google.com") ||
                hostnameMatches(parsedUrl.hostname, "slides.google.com");
        }

        function getGoogleAccessNote(url) {
            if (!isGoogleResource(url)) {
                return "";
            }

            return "This Google Drive or document link may require you to sign in with your BRACU GSuite account.";
        }

        function createSafeExternalLink(url, label, className) {
            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                return null;
            }

            const link = document.createElement("a");
            link.href = parsedUrl.href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.className = className;
            link.textContent = label;
            return link;
        }

        function createPreviewIframe(url, className, allow = "") {
            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                return null;
            }

            const iframe = document.createElement("iframe");
            iframe.src = parsedUrl.href;
            iframe.className = className;
            iframe.referrerPolicy = "strict-origin-when-cross-origin";

            if (allow) {
                iframe.setAttribute("allow", allow);
            }

            return iframe;
        }

        function showFallback(title, message, linkUrl, linkLabel, extraNote = "") {
            resetPdfState();

            const fallback = document.createElement("div");
            fallback.className = "preview-fallback";

            const heading = document.createElement("h3");
            heading.textContent = title;

            const paragraph = document.createElement("p");
            paragraph.textContent = message;

            fallback.append(heading, paragraph);

            if (extraNote) {
                const note = document.createElement("p");
                note.className = "preview-access-note";
                note.textContent = extraNote;
                fallback.appendChild(note);
            }

            const link = createSafeExternalLink(
                linkUrl,
                linkLabel,
                "btn link-btn preview-original-link"
            );

            if (link) {
                fallback.appendChild(link);
            }

            previewBody.replaceChildren(fallback);
        }

        function openModal(fileUrl, fileTitle, downloadUrl = "") {
            const parsedUrl = getSafeHttpUrl(fileUrl);
            openPreviewShell(fileTitle || "File Preview");

            if (!parsedUrl) {
                hideOpenTab();
                hideHeaderDownload();
                showFallback(
                    "Preview unavailable",
                    "The stored file URL is invalid.",
                    window.location.href,
                    "Return to page"
                );
                return;
            }

            const safeFileUrl = parsedUrl.href;

            showOpenTab(safeFileUrl);
            showHeaderDownload(
                downloadUrl || safeFileUrl,
                "Download",
                true
            );

            if (isImageUrl(safeFileUrl)) {
                loadImagePreview(
                    safeFileUrl,
                    fileTitle || "Image Preview"
                );
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


        function loadImagePreview(imageUrl, imageTitle) {
            resetPdfState();

            const viewer = document.createElement("div");
            viewer.className = "image-viewer";

            const toolbar = document.createElement("div");
            toolbar.className = "pdf-toolbar image-toolbar";

            const toolbarLeft = document.createElement("div");
            toolbarLeft.className = "pdf-toolbar-left";

            const toolbarTitle = document.createElement("strong");
            toolbarTitle.textContent = "Image Viewer";
            toolbarLeft.appendChild(toolbarTitle);

            const toolbarRight = document.createElement("div");
            toolbarRight.className = "pdf-toolbar-right";

            const zoomOut = document.createElement("button");
            zoomOut.type = "button";
            zoomOut.className = "pdf-tool-btn";
            zoomOut.id = "imageZoomOut";
            zoomOut.setAttribute("aria-label", "Zoom image out");
            zoomOut.textContent = "−";

            const zoomLabel = document.createElement("span");
            zoomLabel.className = "pdf-zoom-label";
            zoomLabel.id = "imageZoomLabel";
            zoomLabel.textContent = "100%";

            const zoomIn = document.createElement("button");
            zoomIn.type = "button";
            zoomIn.className = "pdf-tool-btn";
            zoomIn.id = "imageZoomIn";
            zoomIn.setAttribute("aria-label", "Zoom image in");
            zoomIn.textContent = "+";

            toolbarRight.append(zoomOut, zoomLabel, zoomIn);
            toolbar.append(toolbarLeft, toolbarRight);

            const scrollContainer = document.createElement("div");
            scrollContainer.className = "image-scroll-container";
            scrollContainer.id = "imageScrollContainer";
            scrollContainer.tabIndex = 0;

            const stage = document.createElement("div");
            stage.className = "image-preview-stage";
            stage.id = "imagePreviewStage";

            const image = document.createElement("img");
            image.className = "image-preview-content";
            image.id = "zoomablePreviewImage";
            image.src = imageUrl;
            image.alt = imageTitle;

            image.addEventListener("load", function () {
                currentImageNaturalWidth = image.naturalWidth;
                currentImageNaturalHeight = image.naturalHeight;
                currentImageScale = 1;
                refreshImageBaseSize();
                updateImageZoom();
            });

            image.addEventListener("error", function () {
                showFallback(
                    "Image loading failed",
                    "The preview could not load this image.",
                    imageUrl,
                    "Open image"
                );
            });

            stage.appendChild(image);
            scrollContainer.appendChild(stage);
            viewer.append(toolbar, scrollContainer);
            previewBody.replaceChildren(viewer);
        }

        function getImageViewportSize() {
            const container = document.getElementById(
                "imageScrollContainer"
            );

            if (!container) {
                return {
                    width: 240,
                    height: 240
                };
            }

            const styles = window.getComputedStyle(container);
            const horizontalPadding =
                parseFloat(styles.paddingLeft || "0") +
                parseFloat(styles.paddingRight || "0");
            const verticalPadding =
                parseFloat(styles.paddingTop || "0") +
                parseFloat(styles.paddingBottom || "0");

            return {
                width: Math.max(
                    240,
                    container.clientWidth - horizontalPadding
                ),
                height: Math.max(
                    180,
                    container.clientHeight - verticalPadding
                )
            };
        }

        function refreshImageBaseSize() {
            if (
                !currentImageNaturalWidth ||
                !currentImageNaturalHeight
            ) {
                return;
            }

            const viewport = getImageViewportSize();
            const fitScale = Math.min(
                viewport.width / currentImageNaturalWidth,
                viewport.height / currentImageNaturalHeight,
                1
            );

            currentImageBaseWidth = Math.max(
                120,
                Math.round(currentImageNaturalWidth * fitScale)
            );
        }

        function updateImageZoom() {
            const container = document.getElementById(
                "imageScrollContainer"
            );
            const stage = document.getElementById(
                "imagePreviewStage"
            );
            const image = document.getElementById(
                "zoomablePreviewImage"
            );
            const label = document.getElementById(
                "imageZoomLabel"
            );

            if (
                !container ||
                !stage ||
                !image ||
                !currentImageBaseWidth ||
                !currentImageNaturalWidth ||
                !currentImageNaturalHeight
            ) {
                return;
            }

            const viewport = getImageViewportSize();
            const aspectRatio =
                currentImageNaturalHeight /
                currentImageNaturalWidth;

            const renderedWidth = Math.max(
                60,
                Math.round(
                    currentImageBaseWidth * currentImageScale
                )
            );
            const renderedHeight = Math.max(
                60,
                Math.round(renderedWidth * aspectRatio)
            );

            const stageWidth = Math.max(
                viewport.width,
                renderedWidth
            );
            const stageHeight = Math.max(
                viewport.height,
                renderedHeight
            );

            stage.style.width = `${stageWidth}px`;
            stage.style.height = `${stageHeight}px`;

            image.style.width = `${renderedWidth}px`;
            image.style.height = `${renderedHeight}px`;
            image.style.left =
                `${Math.round((stageWidth - renderedWidth) / 2)}px`;
            image.style.top =
                `${Math.round((stageHeight - renderedHeight) / 2)}px`;

            if (label) {
                label.textContent =
                    `${Math.round(currentImageScale * 100)}%`;
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

            column.replaceChildren();

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
            previewBody.replaceChildren();
            document.body.style.overflow = "";
            hideOpenTab();
            hideHeaderDownload();
            resetPdfState();
        }

        function getYouTubeEmbedUrl(url) {
            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                return null;
            }

            const hostname = parsedUrl.hostname;

            if (hostnameMatches(hostname, "youtube.com")) {
                const videoId = parsedUrl.searchParams.get("v");

                if (hasSafeId(videoId)) {
                    return `https://www.youtube.com/embed/${encodeURIComponent(videoId)}`;
                }

                if (parsedUrl.pathname.startsWith("/shorts/")) {
                    const shortsId = parsedUrl.pathname.split("/shorts/")[1]?.split("/")[0];

                    if (hasSafeId(shortsId)) {
                        return `https://www.youtube.com/embed/${encodeURIComponent(shortsId)}`;
                    }
                }
            }

            if (hostnameMatches(hostname, "youtu.be")) {
                const videoId = parsedUrl.pathname.split("/").filter(Boolean)[0];

                if (hasSafeId(videoId)) {
                    return `https://www.youtube.com/embed/${encodeURIComponent(videoId)}`;
                }
            }

            return null;
        }

        function getGoogleDrivePreviewUrl(url) {
            const parsedUrl = getSafeHttpUrl(url);

            if (!parsedUrl) {
                return null;
            }

            const hostname = parsedUrl.hostname;

            if (
                hostnameMatches(hostname, "docs.google.com") ||
                hostnameMatches(hostname, "sheets.google.com") ||
                hostnameMatches(hostname, "slides.google.com")
            ) {
                const docMatch = parsedUrl.pathname.match(
                    /\/(document|spreadsheets|presentation)\/d\/([^/]+)/
                );

                if (docMatch && hasSafeId(docMatch[2])) {
                    const docType = docMatch[1];
                    const docId = encodeURIComponent(docMatch[2]);

                    return {
                        type: "google_doc",
                        previewUrl: `https://docs.google.com/${docType}/d/${docId}/preview`
                    };
                }

                return {
                    type: "unknown",
                    previewUrl: parsedUrl.href
                };
            }

            if (!hostnameMatches(hostname, "drive.google.com")) {
                return null;
            }

            const fileMatch = parsedUrl.pathname.match(/\/file\/d\/([^/]+)/);

            if (fileMatch && hasSafeId(fileMatch[1])) {
                return {
                    type: "file",
                    previewUrl: `https://drive.google.com/file/d/${encodeURIComponent(fileMatch[1])}/preview`
                };
            }

            if (parsedUrl.pathname === "/open") {
                const fileId = parsedUrl.searchParams.get("id");

                if (hasSafeId(fileId)) {
                    return {
                        type: "file",
                        previewUrl: `https://drive.google.com/file/d/${encodeURIComponent(fileId)}/preview`
                    };
                }
            }

            const folderMatch = parsedUrl.pathname.match(/\/drive\/folders\/([^/?#]+)/);

            if (folderMatch && hasSafeId(folderMatch[1])) {
                return {
                    type: "folder",
                    previewUrl: `https://drive.google.com/embeddedfolderview?id=${encodeURIComponent(folderMatch[1])}#list`
                };
            }

            return {
                type: "unknown",
                previewUrl: parsedUrl.href
            };
        }

        function openExternalPreview(url, title) {
            const parsedUrl = getSafeHttpUrl(url);
            openPreviewShell(title || "Link Preview");

            if (!parsedUrl) {
                hideOpenTab();
                hideHeaderDownload();
                showFallback(
                    "Preview unavailable",
                    "This link is not a valid HTTP or HTTPS URL.",
                    window.location.href,
                    "Return to page"
                );
                return;
            }

            const safeUrl = parsedUrl.href;

            hideOpenTab();
            showHeaderDownload(safeUrl, "Open Original", false);

            const youtubeEmbedUrl = getYouTubeEmbedUrl(safeUrl);
            const drivePreviewUrl = getGoogleDrivePreviewUrl(safeUrl);
            const googleAccessNote = getGoogleAccessNote(safeUrl);

            if (youtubeEmbedUrl) {
                resetPdfState();

                const videoWrap = document.createElement("div");
                videoWrap.className = "preview-video-wrap";

                const youtubeUrl = new URL(youtubeEmbedUrl);
                youtubeUrl.searchParams.set("rel", "0");
                youtubeUrl.searchParams.set("modestbranding", "1");
                youtubeUrl.searchParams.set("origin", window.location.origin);

                const iframe = createPreviewIframe(
                    youtubeUrl.href,
                    "",
                    "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                );

                if (iframe) {
                    iframe.allowFullscreen = true;
                    videoWrap.appendChild(iframe);
                }

                previewBody.replaceChildren(videoWrap);
            } else if (drivePreviewUrl) {
                resetPdfState();

                if (drivePreviewUrl.type === "file" || drivePreviewUrl.type === "google_doc") {
                    const iframe = createPreviewIframe(
                        drivePreviewUrl.previewUrl,
                        "preview-frame",
                        "autoplay"
                    );

                    if (iframe) {
                        previewBody.replaceChildren(iframe);
                    } else {
                        showFallback(
                            "Preview unavailable",
                            "The Google preview URL is invalid.",
                            safeUrl,
                            "Open original link",
                            googleAccessNote
                        );
                    }
                } else if (drivePreviewUrl.type === "folder") {
                    const folderWrap = document.createElement("div");
                    folderWrap.className = "preview-folder-wrap";

                    const note = document.createElement("p");
                    note.className = "preview-access-note";
                    note.textContent =
                        "This Google Drive folder may require BRACU GSuite access. If the preview does not load properly, use Open Original.";

                    const iframe = createPreviewIframe(
                        drivePreviewUrl.previewUrl,
                        "preview-frame drive-folder-frame"
                    );

                    folderWrap.appendChild(note);

                    if (iframe) {
                        folderWrap.appendChild(iframe);
                    }

                    previewBody.replaceChildren(folderWrap);
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
                loadImagePreview(
                    safeUrl,
                    title || "Image Preview"
                );
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
            const downloadUrl = previewButton.dataset.downloadUrl || "";

            if (!fileUrl) {
                return;
            }

            openModal(fileUrl, fileTitle, downloadUrl);
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
            if (event.target.id === "imageZoomIn") {
                currentImageScale = Math.min(
                    3,
                    Number((currentImageScale + 0.15).toFixed(2))
                );
                updateImageZoom();
                return;
            }

            if (event.target.id === "imageZoomOut") {
                currentImageScale = Math.max(
                    0.5,
                    Number((currentImageScale - 0.15).toFixed(2))
                );
                updateImageZoom();
                return;
            }

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
            clearTimeout(pdfResizeTimer);

            pdfResizeTimer = setTimeout(function () {
                const image = document.getElementById(
                    "zoomablePreviewImage"
                );

                if (image && currentImageNaturalWidth) {
                    refreshImageBaseSize();
                    updateImageZoom();
                }

                if (currentPdf) {
                    refreshPdfBaseWidth();
                    rerenderScrollablePdf();
                }
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

// Browser-local favorites and recently viewed courses.
(function () {
    const FAVORITES_KEY = "studybee_favorite_courses";
    const RECENT_KEY = "studybee_recent_courses";
    const MAX_RECENT_COURSES = 6;
    const button = document.getElementById(
        "courseFavoriteButton"
    );

    if (!button) {
        return;
    }

    const course = {
        id: String(button.dataset.courseId || ""),
        code: button.dataset.courseCode || "",
        title: button.dataset.courseTitle || "",
        url: button.dataset.courseUrl || "",
    };

    function read(key) {
        try {
            const value = JSON.parse(
                localStorage.getItem(key) || "[]"
            );

            return Array.isArray(value) ? value : [];
        } catch (error) {
            return [];
        }
    }

    function write(key, value) {
        try {
            localStorage.setItem(
                key,
                JSON.stringify(value)
            );
        } catch (error) {
            // Storage can be unavailable without breaking the page.
        }
    }

    function isFavorite() {
        return read(FAVORITES_KEY).some(
            (item) => String(item.id) === course.id
        );
    }

    function updateButton() {
        const active = isFavorite();

        button.classList.toggle("active", active);
        button.textContent = (
            active
                ? "★ Favorited"
                : "☆ Favorite"
        );
    }

    function rememberRecent() {
        const recent = read(RECENT_KEY).filter(
            (item) => String(item.id) !== course.id
        );

        recent.unshift(course);
        write(
            RECENT_KEY,
            recent.slice(0, MAX_RECENT_COURSES)
        );
    }

    button.addEventListener("click", function () {
        const favorites = read(FAVORITES_KEY).filter(
            (item) => String(item.id) !== course.id
        );

        if (!isFavorite()) {
            favorites.unshift(course);
        }

        write(FAVORITES_KEY, favorites);
        updateButton();
    });

    rememberRecent();
    updateButton();
})();
