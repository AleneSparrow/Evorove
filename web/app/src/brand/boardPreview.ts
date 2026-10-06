import type { WatchTab } from "../lib/crmBoard";

export type BoardPreviewTab = WatchTab;

export type BoardPreviewMessage = {
  from: "engine" | "person";
  text: string;
};

export type BoardPreviewPerson = {
  id: string;
  name: string;
  summary: string;
  when: string;
  messages: BoardPreviewMessage[];
};

export type BoardPreviewScene = {
  tab: BoardPreviewTab;
  people: BoardPreviewPerson[];
};

/** Static Client 0 scenes for the landing. Same four tabs as the live board.
 * Not a conversion claim, not a live log, not a screenshot of a finished UI. */
export const BOARD_PREVIEW_SCENES: Record<BoardPreviewTab, BoardPreviewScene> = {
  cold: {
    tab: "cold",
    people: [
      {
        id: "lena",
        name: "Lena Brooks",
        summary: "Public studio site. Fits the offer. Not written yet.",
        when: "just now",
        messages: [],
      },
      {
        id: "chris",
        name: "Chris Nguyen",
        summary: "Open listing, no closer on staff. Not written yet.",
        when: "2h",
        messages: [],
      },
    ],
  },
  in_progress: {
    tab: "in_progress",
    people: [
      {
        id: "jordan",
        name: "Jordan Hale",
        summary: "Replied. The engine is in the thread.",
        when: "12m",
        messages: [
          {
            from: "engine",
            text: "Jordan — Thursday still sits empty. Evorove finds people in the open web, puts them on Cold, and writes until Done. You watch.",
          },
          {
            from: "person",
            text: "I already have a CRM. I don't need another inbox.",
          },
          {
            from: "engine",
            text: "This isn't an inbox. Cold is people not written yet. The engine writes first and stays until Done. You don't hop in to close.",
          },
        ],
      },
      {
        id: "dana",
        name: "Dana Wolff",
        summary: "Asked how people land on Cold.",
        when: "1h",
        messages: [
          {
            from: "person",
            text: "Where do these people even come from?",
          },
          {
            from: "engine",
            text: "The open web — public places your audience already lives. Fit the profile, then Cold. Not a form on your site.",
          },
        ],
      },
    ],
  },
  offer_made: {
    tab: "offer_made",
    people: [
      {
        id: "priya",
        name: "Priya Shah",
        summary: "Value named. Not closed.",
        when: "3h",
        messages: [
          {
            from: "person",
            text: "If it actually runs the sale, what do I pay?",
          },
          {
            from: "engine",
            text: "Seven days on the board. Then $199 a month — instead of a hire. The payment link is the Evorove subscription.",
          },
        ],
      },
    ],
  },
  done: {
    tab: "done",
    people: [
      {
        id: "sam",
        name: "Sam Ortiz",
        summary: "Paid on the business link.",
        when: "yesterday",
        messages: [
          {
            from: "person",
            text: "Send the link.",
          },
          {
            from: "engine",
            text: "Sent. Same board, same rules. You stay on watch.",
          },
        ],
      },
    ],
  },
};

export const BOARD_PREVIEW_TABS = ["cold", "in_progress", "offer_made", "done"] as const satisfies readonly BoardPreviewTab[];

export const BOARD_PREVIEW_DEFAULT_TAB: BoardPreviewTab = "in_progress";

export const BOARD_PREVIEW_CAPTION = "Client 0 board · architecture preview";

export const BOARD_PREVIEW_HOLD_MS: Record<BoardPreviewTab, number> = {
  cold: 2800,
  in_progress: 5600,
  offer_made: 4000,
  done: 3200,
};

export function nextBoardPreviewTab(tab: BoardPreviewTab): BoardPreviewTab {
  const index = BOARD_PREVIEW_TABS.indexOf(tab);
  return BOARD_PREVIEW_TABS[(index + 1) % BOARD_PREVIEW_TABS.length];
}

export function boardPreviewCounts(): Record<BoardPreviewTab, number> {
  return Object.fromEntries(
    BOARD_PREVIEW_TABS.map((tab) => [tab, BOARD_PREVIEW_SCENES[tab].people.length]),
  ) as Record<BoardPreviewTab, number>;
}

export function boardPreviewPerson(
  scene: BoardPreviewScene,
  personId: string,
): BoardPreviewPerson {
  return scene.people.find((person) => person.id === personId) ?? scene.people[0];
}

export function flattenBoardPreviewCopy(): string {
  return BOARD_PREVIEW_TABS.flatMap((tab) =>
    BOARD_PREVIEW_SCENES[tab].people.flatMap((person) => [
      person.name,
      person.summary,
      ...person.messages.map((message) => message.text),
    ]),
  ).join("\n");
}
