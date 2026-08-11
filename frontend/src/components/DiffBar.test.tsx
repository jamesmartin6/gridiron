import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiffBar } from "./DiffBar";

describe("DiffBar", () => {
  it("renders a positive value with the positive fill class", () => {
    const { container } = render(
      <DiffBar label="Win %" value={0.2} clamp={1} format={(v) => v.toFixed(2)} />
    );
    expect(screen.getByText("0.20")).toBeInTheDocument();
    expect(container.querySelector(".diff-fill.positive")).toBeInTheDocument();
  });

  it("renders a negative value with the negative fill class", () => {
    const { container } = render(
      <DiffBar label="Win %" value={-0.2} clamp={1} format={(v) => v.toFixed(2)} />
    );
    expect(container.querySelector(".diff-fill.negative")).toBeInTheDocument();
  });

  it("clamps magnitude to 50% of the track width", () => {
    const { container } = render(
      <DiffBar label="EPA" value={10} clamp={1} format={(v) => String(v)} />
    );
    const fill = container.querySelector(".diff-fill") as HTMLElement;
    expect(fill.style.width).toBe("50%");
  });

  it("renders a placeholder when value is null", () => {
    render(<DiffBar label="Win %" value={null} clamp={1} format={(v) => String(v)} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
