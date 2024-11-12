document.addEventListener('DOMContentLoaded', function() {
    // Target all fields with class 'transition-conditions'
    document.querySelectorAll('.transition-conditions').forEach(function(element) {
        // Wrap the text content in a <code> block for syntax highlighting
        const codeBlock = document.createElement('code');
        codeBlock.className = 'language-python'; // Specify Python syntax
        codeBlock.textContent = element.value;

        // Replace the textarea with a <pre><code> structure
        const pre = document.createElement('pre');
        pre.appendChild(codeBlock);

        // Insert the highlighted code
        element.parentNode.replaceChild(pre, element);

        // Highlight the code using Prism
        Prism.highlightElement(codeBlock);
    });
});
