# Preface

---

## The AI Explosion
- Scaling laws predict better models from faster hardware and bigger data, but the real surprise was the explosion of applications.
- Lowered entry barriers now allow developers to build applications without writing code, transforming AI into a universal tool.
- Adoption builds on decades-old techniques like language modeling (1950s) and retrieval systems, yet scale creates new challenges.

## Core Engineering Principles
- Best practices from traditional ML—systematic experimentation, rigorous evaluation, and optimization—remain essential for foundation models.
- Familiarity can mislead engineers into thinking nothing is new, but increased model scale introduces unique opportunities and hurdles.
- The book covers adapting foundation models end-to-end by combining tried-and-true techniques with emerging solutions.

## Author's Learning Journey
- Insights were gathered from projects, papers, and interviews with researchers from major labs like OpenAI and Google.
- Over 100 conversations included framework developers, executives, product managers, and independent application builders.
- The book synthesizes these notes to guide the end-to-end process of adapting foundation models for real-world problems.

---

## Core Purpose & Framework
- Provides a framework for adapting foundation models (LLMs and LMMs) to specific applications.
- Answers critical questions like "Should I build this?" and "How do I evaluate my application?".
- Covers best practices for prompt engineering, RAG strategies, agents, finetuning, and data validation.

## Authoritative Fundamentals
- Draws on a decade of experience with language models and ML systems, illustrated by case studies.
- Focuses on three enduring fundamentals that outlast rapidly changing tools and APIs.
- Includes ample references and content extensively reviewed by experts from diverse backgrounds.

## Relationship with DMLS
- Serves as a companion to *Designing Machine Learning Systems*, focusing on foundation models vs. traditional ML.
- Both books are self-contained; AIE covers topics in DMLS but with less depth where applicable.
- Addresses the overlap between traditional and AI engineering, noting that real-world systems often involve both.

---

## What This Book Is Not

*   **Not a tutorial**: Offers a framework for selecting tools rather than teaching specific tool usage or pseudocode implementation.
*   **Not an ML theory book**: Focuses on practical application building instead of explaining neural networks or training from scratch.
*   **No prior ML required**: Readers can succeed without background, though understanding probabilistic concepts aids effectiveness.

---

## Approach to Problem Solving

*   **Start simple**: Analyzes fundamental challenges by progressing from simplest solutions to complex ones as needed.
*   **Consult experts**: Relies on a network of researchers and engineers to identify important problems and solutions.
*   **Apply Lindy's Law**: Infers future technology longevity based on current age, assuming established tech will persist longer.

---

## Temporary Concepts Included

*   **Immediate utility**: Includes concepts useful for specific application developers even if they are temporary.
*   **Illustrative value**: Features concepts that demonstrate interesting problem-solving approaches despite potential obsolescence.

---

## Target Audience Overview
This technical book targets AI engineers, ML engineers, data scientists, and technical product managers leveraging foundation models. It covers core concepts like supervision, gradient descent, backpropagation, loss functions, and hyperparameter tuning. Readers should be familiar with neural architectures (feedforward, recurrent, transformer) and metrics (accuracy, F1, cosine similarity).

## Practical Application Scenarios
The book supports building or optimizing AI applications from scratch to production-ready stages. It addresses challenges like hallucinations, security, latency, and costs while offering targeted solutions. Readers can streamline team development processes to make them more systematic, faster, and reliable.

## Strategic Business Impact
Learn how organizations leverage foundation models to improve the bottom line and build effective technical teams. Tool developers identify underserved areas in AI engineering to position their products within the ecosystem. Researchers gain deeper understanding of practical AI use cases for better application development.

---

## Navigating the Book Structure
- The book follows the typical AI application development process, from decision-making to end-to-end deployment.
- Modules cover skills for AI engineers, capabilities/limitations of AI, and technical deep dives.
- Readers can skip sections they are familiar with; early readers may find some technical details too dense.

---

## Core Development Chapters Overview
- **Chapters 3 & 4**: Evaluate reliability and build systematic pipelines using different evaluation methods.
- **Chapter 5**: Master prompt engineering, best practices, and defenses against malicious prompt attacks.
- **Chapter 6**: Optimize responses using context construction patterns like RAG and agentic workflows.

---

## Advanced Optimization & Deployment
- **Chapter 7**: Adapt models via finetuning and model merging while managing memory-intensive requirements.
- **Chapter 8**: Acquire, annotate, and process high-quality data essential for effective model training.
- **Chapter 9**: Optimize inference costs and speed at both the model and service levels; design user feedback systems.

---

## Typographical Styles
- Italics indicate new terms, URLs, emails, filenames, and extensions.
- Constant width denotes program listings and code elements like variables.
- Bold constant width shows commands to be typed literally by users.
- Italicized constant width marks placeholders for user-supplied values.

---

## Formatting Hierarchy
- **Bold**: Used for emphasis or critical actions requiring immediate attention.
- *Italic*: Highlights new terminology, web addresses, and file identifiers.
- `Monospace`: Displays code blocks and specific programmatic references.
- **`Monospace Bold`**: Designates commands that must be entered exactly as shown.

---

## Markdown Elements
- **TIP**: Signifies a tip or suggestion for readers.
- **NOTE**: Indicates a general note or observation.
- **WARNING**: Alerts users to potential risks or cautions.
- These elements guide reader attention and provide context.

---

## Code Example Resources
- Supplemental code, exercises, and papers are hosted on GitHub.
- The repository covers deep AI engineering topics beyond the book's scope.
- It includes behind-the-scenes writing process information and statistics.
- Technical support for code examples is available via email.

---

## License & Usage Rights
* Use example code freely for programs and documentation without permission unless reproducing significant portions.
* Selling or distributing examples from O'Reilly books requires explicit permission.
* Citing the book and quoting code in answers does not require permission.
* Significant incorporation of code into product documentation requires permission.

## Attribution Guidelines
* Attribution is appreciated but generally not required for standard use.
* Preferred attribution includes title, author, publisher, and ISBN (e.g., _AI Engineering_ by Chip Huyen).
* Contact permissions@oreilly.com if your use falls outside fair use or granted permissions.

---

## O'Reilly History & Mission
* O'Reilly Media has provided technology training and insight for over 40 years.
* The goal is to help companies succeed through knowledge and business training.

---

## Contact O'Reilly Media
Address inquiries to O’Reilly Media, Inc. at 1005 Gravenstein Highway North, Sebastopol, CA 95472.
Call 800-889-8969 for US/Canada or 707-827-7019 for international/local lines.
Send emails to support@oreilly.com or visit https://oreilly.com/about/contact.html.

---

## O'Reilly Expert Network
Experts share knowledge through books, articles, and the online learning platform.
The platform offers live training courses, learning paths, and interactive coding environments.
Access content from O’Reilly and 200+ other publishers on-demand.

---

## Book Resources & Contact Info
*   Access errata, examples, and book news at https://oreil.ly/aiengineering.
*   Follow O'Reilly Media on LinkedIn, YouTube, and visit their main website for courses.
*   The web page lists updates and additional information regarding the book's content.

---

## Key Contributors & Technical Reviewers
*   Luke Metz and Han-chung Lee provided early technical reviews and prevented wrong paths.
*   Vittorio Cretella and Andrei Lopatenko offered deep expertise from Fortune 500 AI leadership.
*   Eugene Yan, Shawn Wang, and Sanyam Bhutani gave critical technical and emotional support.

---

## Editorial Team & Career Lessons
*   Development editors Melissa Potter, Corbin Collins, and Jill Leonard shaped the book's structure.
*   Production editor Elizabeth Kelly and copyeditor Liz Wheeler ensured quality production standards.
*   The author learned that tools become outdated quickly and that better language models are essential.
