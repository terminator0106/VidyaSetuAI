const mockResponses = [
  "Great question! Let me break this down step by step.\n\nFirst, let's understand the basic concept. This topic relates to how energy is transferred between objects. Think of it like passing a ball — the energy moves from one place to another.\n\n**Key Points:**\n1. Energy cannot be created or destroyed\n2. It can only change form\n3. The total energy in a closed system stays the same\n\nWould you like me to explain any of these points in simpler terms?",
  "That's a really thoughtful question! Here's how I'd explain it:\n\nImagine you're pouring water from one glass to another. The amount of water doesn't change — it just moves. That's similar to how this concept works.\n\n**In simple terms:**\n- The process starts when the input is received\n- It goes through a series of changes\n- The output is always predictable if you know the rules\n\nShall I give you a real-world example from your textbook?",
  "Let me explain this in a way that's easy to remember.\n\n**Think of it like a recipe:**\n1. You start with your ingredients (the given information)\n2. You follow the steps (apply the formula)\n3. You get your dish (the answer)\n\n**The formula is:** Result = Input × Factor\n\nThis saves you from memorizing everything — just understand the pattern!\n\nWant me to walk through a practice problem?",
];

export async function askQuestion(question: string): Promise<string> {
  await new Promise((r) => setTimeout(r, 1500 + Math.random() * 1000));
  return mockResponses[Math.floor(Math.random() * mockResponses.length)];
}
