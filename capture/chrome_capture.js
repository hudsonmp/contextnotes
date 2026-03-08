/**
 * Chrome reading context capture.
 *
 * Injected into the active tab via claude-in-chrome MCP's javascript_tool.
 * Captures viewport state, visible paragraphs, and the most-centered paragraph
 * (the one the user is most likely reading).
 *
 * Returns a ReadingSource-compatible object with W3C WADM TextQuoteSelector
 * for the focus paragraph.
 */

(function captureReadingContext() {
  const vh = window.innerHeight;
  const vw = window.innerWidth;
  const docHeight = document.documentElement.scrollHeight;
  const scrollY = window.scrollY;
  const scrollProgress = docHeight > vh
    ? scrollY / (docHeight - vh)
    : 0;

  // Collect all content elements
  const selectors = 'p, h1, h2, h3, h4, h5, h6, li, blockquote, figcaption, td';
  const elements = document.querySelectorAll(selectors);

  const visible = [];
  let bestParagraph = null;
  let bestCenterDist = Infinity;

  elements.forEach((el, i) => {
    const rect = el.getBoundingClientRect();
    const text = el.textContent.trim();

    // Skip empty or tiny elements
    if (!text || text.length < 10) return;

    // Check if in viewport
    if (rect.top < vh && rect.bottom > 0) {
      const truncated = text.slice(0, 200);
      visible.push({ index: i, text: truncated });

      // Find the most-centered paragraph (likely reading focus)
      const centerDist = Math.abs((rect.top + rect.bottom) / 2 - vh / 2);
      if (centerDist < bestCenterDist) {
        bestCenterDist = centerDist;

        // Build W3C WADM TextQuoteSelector
        // Get surrounding text for prefix/suffix context
        const allText = document.body.innerText;
        const textStart = allText.indexOf(text.slice(0, 50));
        let prefix = null;
        let suffix = null;

        if (textStart > 0) {
          prefix = allText.slice(Math.max(0, textStart - 50), textStart).trim();
        }
        if (textStart >= 0) {
          const textEnd = textStart + text.length;
          suffix = allText.slice(textEnd, textEnd + 50).trim();
        }

        bestParagraph = {
          index: i,
          text: text,
          selector: {
            type: "TextQuoteSelector",
            exact: text.slice(0, 500),
            prefix: prefix ? prefix.slice(-100) : null,
            suffix: suffix ? suffix.slice(0, 100) : null
          }
        };
      }
    }
  });

  // Capture any user selection
  const selection = window.getSelection();
  const selectedText = selection && selection.toString().trim() ? selection.toString().trim() : null;

  return {
    url: window.location.href,
    title: document.title,
    timestamp: new Date().toISOString(),
    viewport: {
      scroll_y: scrollY,
      scroll_progress: Math.round(scrollProgress * 1000) / 1000,
      viewport_height: vh,
      document_height: docHeight
    },
    visible_paragraphs: visible,
    focus_paragraph: bestParagraph,
    selector: bestParagraph ? bestParagraph.selector : null,
    selection: selectedText
  };
})();
