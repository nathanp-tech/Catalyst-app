# Catalyst 🚀

**Catalyst** is an intelligent tutoring system designed as a research prototype for a Master's thesis in Education. It serves as a smart pedagogical assistant, aiming to transform how students interact with mathematical exercises and how teachers analyze their progress. By leveraging a Socratic AI tutor and powerful data analytics, Catalyst turns student errors into valuable learning opportunities.

## Core Mission & Pedagogical Approach

The foundational goal of Catalyst is to explore the synergy between artificial intelligence and modern pedagogical strategies. The project is built on the premise that errors are not failures, but crucial stepping stones in the learning process.

Our pedagogical approach is centered around these key principles:

1.  **Socratic Method**: The AI tutor never gives the direct answer. Instead, it guides students through a series of thought-provoking questions, helping them build their own understanding and correct their own mistakes. This fosters critical thinking and deep, lasting comprehension.
2.  **Constructivism**: Students actively construct their knowledge by interacting with the material. The interactive whiteboard is a digital canvas where they can externalize their thought processes, test hypotheses, and visualize solutions.
3.  **Data-Driven Pedagogy**: For teachers, Catalyst provides actionable insights. By automatically analyzing student work, the platform helps educators move from simple grading to detailed diagnostic analysis, enabling them to tailor their support to the specific needs of each student and the class as a whole.
4.  **Teacher-AI Collaboration**: Catalyst is not designed to replace the teacher, but to augment their capabilities. Features like the "Co-Analysis" dashboard encourage a collaborative review process, where the teacher's expertise is combined with the AI's analytical power.

---

## Key Features

Catalyst offers a distinct set of features tailored to the needs of both students and teachers.

### For Students: The Learning Environment

*   **Interactive AI Tutor**: A friendly and encouraging tutor that provides real-time guidance on mathematical exercises.
*   **Socratic Dialogue**: The AI asks questions to stimulate reflection rather than providing ready-made answers.
*   **Digital Whiteboard**: A feature-rich workspace with tools for drawing, writing, and creating shapes, allowing students to solve problems just as they would on paper.
*   **Gamified Progression**: A personal dashboard tracks progress, session duration, and awards badges for milestones, making learning more engaging.
*   **Error Analysis Dashboard**: Students can view charts of their common error types, helping them become more aware of their own learning patterns.

### For Teachers: The Pedagogical Cockpit

*   **Class Dashboard**: A centralized view of student activity and performance, with the ability to filter by class and exercise.
*   **Automated Session Summaries**: Once a student completes a session, the AI generates a concise summary, including:
    *   **Error Analysis**: A quantitative breakdown of error types (e.g., calculation, procedural, conceptual).
    *   **Qualitative Summary**: A short text describing the student's journey, their struggles, and their progress.
*   **AI-Powered Group Creation**: An innovative tool that helps teachers form student groups (heterogeneous or homogeneous) based on performance data and AI-driven suggestions.
*   **Co-Analysis Interface**: A unique dashboard where teachers can compare their own diagnostic of a student's work against the AI's analysis, fostering a reflective practice.
*   **Detailed Session Review**: Teachers can replay any student session, viewing the complete chat history and the final state of the whiteboard.
*   **Curriculum Management**: A structured interface to organize exercises by grade, chapter, and topic, and to upload new material.

---

## Technical Architecture

Catalyst is a modern web application built with a robust and scalable stack.

*   **Backend**:
    *   **Framework**: Django
    *   **APIs**: Django REST Framework for creating a clear separation between the frontend and backend logic.
    *   **AI Integration**: The OpenAI API (using the `gpt-4o` model) is used for all intelligent features, including the Socratic dialogue, session summaries, and group creation logic.
    *   **Database**: SQLite for development, with the flexibility to switch to PostgreSQL for production.

*   **Frontend**:
    *   **Templating**: Standard Django templates with HTML5 and CSS3.
    *   **JavaScript**: Vanilla JavaScript is used to manage the dynamic and interactive components of the application.
    *   **Whiteboard**: The Fabric.js library powers the interactive canvas.
    *   **PDF Rendering**: PDF.js is used to display exercise documents.

*   **Core Application Structure**:
    *   `core`: Main project settings, URLs, and the base templates.
    *   `users`: Manages user authentication (signup, login, logout) and profiles.
    *   `documents`: Handles the storage, categorization, and management of exercise files (PDFs).
    *   `tutor`: The heart of the application, containing the AI interaction logic, the whiteboard interface, and session management.
    *   `dashboard`: Provides all the views and APIs for the student and teacher dashboards.

---

## Getting Started

Follow these instructions to set up and run the project locally.

### Prerequisites

*   Python 3.9+
*   Django 4.2+
*   An OpenAI API key

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/catalyst.git
    cd catalyst
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Set up environment variables:**
    Create a `.env` file in the project root directory (next to `manage.py`) and add your OpenAI API key:
    ```
    OPENAI_API_KEY='your-openai-api-key'
    ```

4.  **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```

5.  **Create a superuser:**
    This will allow you to access the Django admin interface.
    ```bash
    python manage.py createsuperuser
    ```

6.  **Create user groups:**
    For the application to work correctly, you need to create a "Professeurs" (Teachers) group.
    *   Run the server (`python manage.py runserver`).
    *   Navigate to the admin panel (`/admin/`).
    *   Go to "Groups" and create a new group named exactly `Professeurs`.
    *   Assign your superuser (and any other teacher accounts) to this group.

### Running the Application

1.  **Start the development server:**
    ```bash
    python manage.py runserver
    ```

2.  **Access the application:**
    Open your web browser and go to `http://127.0.0.1:8000/`.

---

## Future Work & Research Directions

As a research prototype, Catalyst opens up several avenues for future exploration:

*   **Long-Term Student Modeling**: Track student progress over longer periods to build a more sophisticated model of their strengths and weaknesses.
*   **Adaptive Exercises**: Dynamically adjust the difficulty or type of the next exercise based on the student's performance.
*   **Enhanced Teacher-AI Collaboration**: Develop more sophisticated tools for co-analysis, allowing teachers to give direct feedback to the AI on the quality of its summaries.
*   **Multi-Modal Feedback**: Allow the AI to generate visual feedback directly on the student's whiteboard.