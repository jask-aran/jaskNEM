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
3. wattclarity.com.au
4. https://wattclarity.com.au/articles/2025/01/opening-the-black-box-a-beginners-guide-to-wholesale-market-modelling-part-1/
5. currentlyspeaking.substack.com
6. nemlog.substack.com
7. benbeattie.substack.com


Reading sequence
Given where you are in the learning plan, the order that will compound fastest:

WattClarity Beginner's Guide → Intermediate Guide → Price Setting Concepts (understand how prices actually get set before building 1.3)
Endgame Economics three-part series (understand where your PyPSA model fits in the modelling hierarchy)
Open Electricity Economics chapters 4 and 5 (theoretical grounding for shadow prices and capacity mix)
Full Matthew Davis MMS guide (fill in data gotchas as you hit them in 1.2)
nempy docs and examples (when you're ready to model dispatch more precisely than PyPSA allows)