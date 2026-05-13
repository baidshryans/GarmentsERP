import React from 'react';

export const FieldContainer = ({ children }) => {
  const uid = React.useId();

  const childArray = React.Children.toArray(children);

  // Only wire up htmlFor/id when there is a direct <Input> sibling �
  // for Select / Controller children we skip it to avoid a dangling `for`
  // attribute that would trigger a different browser warning.
  const hasDirectInput = childArray.some(
    (child) => React.isValidElement(child) && child.type?.displayName === 'Input'
  );

  return (
    <div className="flex flex-col gap-1 w-full">
      {childArray.map((child, idx) => {
        if (!React.isValidElement(child))
          return <React.Fragment key={idx}>{child}</React.Fragment>;

        const dn = child.type?.displayName ?? '';

        // Inject htmlFor into the Label � only when a matching Input exists
        if (hasDirectInput && (dn === 'Label' || dn === 'LabelPrimitive.Root')) {
          return React.cloneElement(child, { key: idx, htmlFor: uid });
        }

        // Inject id into the direct Input
        if (dn === 'Input') {
          return React.cloneElement(child, { key: idx, id: uid });
        }

        return <React.Fragment key={idx}>{child}</React.Fragment>;
      })}
    </div>
  );
};

export function arrayToObject(arr, keyField, valueField) {
  return arr.reduce((obj, item) => {
    obj[item[keyField]] = item[valueField];
    return obj;
  }, {});
}

export const evaluateFormula = (formula, data) => {
  try {
    // Handle nested SUM operations first
    let processedFormula = formula.replace(/SUM\(([^)]+)\)/g, (match, path) => {
      const parts = path.trim().split('.');
      let array = data[parts[0]];

      if (!Array.isArray(array)) return 0;
      const sum = array.reduce((acc, item) => {
        return parseFloat(acc) + parseFloat(item[parts[1]]);
      }, 0);
      return sum;
    });

    processedFormula = processedFormula.replace(/(\b[A-Za-z_][A-Za-z0-9_]*\b)|('[^']*')|(\d+)/g, (match, variable, quoted, number) => {
      if (quoted) return quoted; // Preserve anything inside single quotes
      if (number) return number; // Preserve numbers as they are

      if (data.hasOwnProperty(variable)) {
        let value = data[variable];
        return typeof value === "number" ? `(${value})` : `'${value}'`;
      }

      return "0"; // Default replacement if variable is not found
    });




    // Evaluate the final expression
    return parseFloat(new Function(`return ${processedFormula};`)())?.toFixed(2);
  } catch (error) {
    console.error("Formula evaluation error:", error);
    return "";
  }
};

export const renderErrorTree = (errorObj) => {
  return Object.entries(errorObj).map(([key, value], index) => {
    if (Array.isArray(value)) {
      // Either a list of strings or a list of objects (nested)
      if (typeof value[0] === "string") {
        return (
          <div key={`${key}-${index}`} className="ml-2">
            <strong>{key}</strong>:{" "}
            <ul className="list-disc ml-4">
              {value.map((msg, i) => (
                <li key={i}>{msg}</li>
              ))}
            </ul>
          </div>
        );
      } else {
        // It's a list of objects, so we map each
        return (
          <div key={`${key}-${index}`} className="ml-2">
            <strong>{key}</strong>:
            <div className="ml-4 space-y-1">
              {value.map((nestedObj, i) => (
                <div key={i} className="border-l border-gray-300 pl-2">
                  <div className="text-sm text-gray-500">#{i + 1}</div>
                  {renderErrorTree(nestedObj)}
                </div>
              ))}
            </div>
          </div>
        );
      }
    } else if (typeof value === "object") {
      return (
        <div key={`${key}-${index}`} className="ml-2">
          <strong>{key}</strong>:
          <div className="ml-4">{renderErrorTree(value)}</div>
        </div>
      );
    }
    return (
      <div key={`${key}-${index}`} className="ml-2">
        <strong>{key}</strong>: {String(value)}
      </div>
    );
  });
};

