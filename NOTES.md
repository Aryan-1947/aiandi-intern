\# Notes



\## How to run



1\. Copy `cloud-flare.sh` to `cloud-flare.local.sh` and put in your Cloudflare account ID and API token. This file is git-ignored.

2\. Round 1 (clef-flash, original criteria):

&#x20;  python classify.py --model clef-flash --criteria v1 --input comments.json --output results.html

3\. Round 2 (clef, improved criteria):

&#x20;  python classify.py --model clef --criteria v2 --input comments-v2.json --output results-v2.html



Python 3, standard library only.



\## Tools and models used



\- Claude (Anthropic) helped me write classify.py and guided me through the setup.

\- Cloudflare Workers AI: clef-flash for round 1, clef for round 2.

\- Git and GitHub.

\- I read every comment and wrote MISTAKES.md and MISTAKES-v2.md myself.



\## What I changed between rounds



In round 1, clef-flash marked a few toxic comments as acceptable. These were an insult to the TA, a sexist comment about girls getting marks, and a comment that stereotyped a group of students.



So for round 2 I made a new set of criteria called v2. The old one (v1) is still in the script, and I can run it with `--criteria v1`.



In v2, I made toxic mean disrespect towards people, not towards ideas. It covers insulting the TA or a named person, saying someone gets marks or fails because of their gender, region, college or hostel, and general bad remarks about a whole group. I also added that a comment can still be toxic even if it sounds polite. Normal criticism of the work, the course or grading stays acceptable, and sharing your own assignment or a useful free link is not spam.


\## What I found

&#x20;

In round 1 comments were toxic but clef-flash flagged them as acceptable mostly because those comments didn't use any harsh words or languages.


For round 2 clef performed a little better, maybe because it is a larger model, but it was still wrong on a few comments as this round was harder too. I changed both the model and the criteria in round 2, so I can't tell which one made the difference.


\## What I felt about the task



It was a great experience. I learned how a model’s results can improve with proper evaluation and better instructions.

