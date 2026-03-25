1. What if the WA grid was connected to the NEM?
2. How accurate are the MMSDMPS forecasts for the next 5 mins and further?
3. Are rebidding justifications being taken advantage of?
4. To what degree is the NEM/ Australia capacity constrained beyond other markets, and what does that mean for having a dispatch engine
5. A gentailer's retail operations desire low wholesale prices, while its generation arm desires high prices. How do they coordinate bidding across their portfolio, and does that constitutes market manipulation? (Ongoing regulatory question.)
6. To what degree do Energy Asset Operators rely on heuristics or manual dispatch decisions? https://adgefficiency.com/blog/energy-py-linear/
7. How do we get from modeled competitive market price (lower bound) to realised prices in the dispatched model
8. NEMDE MILP Solve takes ~30 seconds, would the market be more efficient if this solve took less time?
9. How does the introduction of batteries change the market constraint that energy cannot be stored, and how will an increasing amount of storage capacity change the market structure?

Constraints: AEMO does not just intersect supply and demand curves. Australia's grid is far more constrained than most, so AEMO's optimiser, the "NEM Dispatch Engine" (NEMDE) incorporates hundreds of constraints for system strength, transmission line capacity etc. The definition and evaluation of these is in the data.



## Info Sources
1. https://www.mdavis.xyz/mms-guide/
2. https://adgefficiency.com/blog/hackers-aemo/
