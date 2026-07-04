import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ModeChooser from "./ModeChooser";

describe("ModeChooser", () => {
  it("renders both options", () => {
    render(<ModeChooser onSelect={() => {}} />);
    expect(screen.getByText(/new erp/i)).toBeInTheDocument();
    expect(screen.getByText(/migrate/i)).toBeInTheDocument();
  });

  it("calls onSelect('new') when the new-ERP card is clicked", () => {
    const onSelect = vi.fn();
    render(<ModeChooser onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /new erp/i }));
    expect(onSelect).toHaveBeenCalledWith("new");
  });

  it("calls onSelect('migrate') when the migrate card is clicked", () => {
    const onSelect = vi.fn();
    render(<ModeChooser onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /migrate/i }));
    expect(onSelect).toHaveBeenCalledWith("migrate");
  });
});
