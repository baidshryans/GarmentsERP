import { createRoot } from 'react-dom/client'
import '../../index.css'


export const openAndPrint = (printComponent) => {

    const newWindow = window.open("", "_blank", "width=800,height=600");

    if (newWindow) {
        const styleSheets = [...document.styleSheets];
        let cssContent = "";

        styleSheets.forEach((sheet) => {
          try {
            if (sheet.cssRules) {
              for (let rule of sheet.cssRules) {
                cssContent += rule.cssText + "\n";
              }
            }
          } catch (e) {
            console.warn("Could not access CSS rules:", e);
          }
        });

        newWindow.document.head.innerHTML = '<meta charset="utf-8">';
        const styleTag = newWindow.document.createElement("style");
        styleTag.textContent = cssContent;
        newWindow.document.head.appendChild(styleTag);

        const rootElement = newWindow.document.createElement("div");
        rootElement.id = "new-root";
        newWindow.document.body.innerHTML = '';
        newWindow.document.body.appendChild(rootElement);

        try {
          createRoot(rootElement).render(printComponent);
          setTimeout(() => { newWindow.print(); }, 500);
        } catch (e) {
          console.error("Print render error:", e);
          newWindow.document.body.innerHTML = '<p>Error rendering print preview. Check console for details.</p>';
        }
    } else {
      alert("Failed to open a new window. Please check your browser settings or disable popup blocker.");
    }
  };
