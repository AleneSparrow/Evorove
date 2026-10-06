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
            text: "Jordan — your Thursday hours still sit empty. Evorove finds people in the open web, puts them on Cold, and writes until Done. You watch the board.",
          },
          {
            from: "person",
            text: "I already have a CRM. I don't need another inbox.",
          },
          {
            from: "engine",
            text: "This isn't an inbox. Cold is people who have not been written yet. The engine writes first and stays until the sale is done. You don't hop in to close.",
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
            text: "Seven days on the board. After that, $199 a month — instead of a hire. The payment link is the Evorove subscription. Say the word and it is yours.",
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
            text: "It's on its way. Same board. Same rules. You stay on watch.",
          },
        ],
      },
    ],
  },
};

export const BOARD_PREVIEW_TABS = ["cold", "in_progress", "offer_made", "done"] as const satisfies readonly BoardPreviewTab[];

export const BOARD_PREVIEW_DEFAULT_TAB: BoardPreviewTab = "in_progress";

export const BOARD_PREVIEW_CAPTION = "Client 0 board · architecture preview";

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
