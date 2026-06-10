// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from "vitest";
import {
  getDensity,
  getSaves,
  getVote,
  setDensity,
  setVote,
  toggleSave,
  type SavedItem,
} from "@/lib/local";

const saved: SavedItem = {
  key: "arxiv:1",
  title: "Paper",
  url: "https://arxiv.org/abs/1",
  source: "arxiv",
  date: "2026-06-08",
};

beforeEach(() => localStorage.clear());

describe("density", () => {
  it("defaults to cards and persists", () => {
    expect(getDensity()).toBe("cards");
    setDensity("compact");
    expect(getDensity()).toBe("compact");
  });
});

describe("votes", () => {
  it("defaults to 0, persists, and clears", () => {
    expect(getVote("arxiv:1")).toBe(0);
    setVote("arxiv:1", 1);
    expect(getVote("arxiv:1")).toBe(1);
    setVote("arxiv:1", 0);
    expect(getVote("arxiv:1")).toBe(0);
  });
});

describe("saves", () => {
  it("toggles on and off", () => {
    expect(toggleSave(saved)).toBe(true);
    expect(getSaves()).toEqual([saved]);
    expect(toggleSave(saved)).toBe(false);
    expect(getSaves()).toEqual([]);
  });
});
