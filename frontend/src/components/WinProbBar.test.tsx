import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WinProbBar } from "./WinProbBar";

describe("WinProbBar", () => {
  it("renders the probability as a rounded percentage", () => {
    render(<WinProbBar prob={0.6234} />);
    expect(screen.getByText("62.3%")).toBeInTheDocument();
  });

  it("sets the fill width proportional to the probability", () => {
    const { container } = render(<WinProbBar prob={0.4} />);
    const fill = container.querySelector(".prob-bar-fill") as HTMLElement;
    expect(fill.style.width).toBe("40%");
  });
});
