document.addEventListener("DOMContentLoaded", () => {
    const tableBody = document.querySelector("#transcriptions-table tbody");
    const modal = document.getElementById("transcription-modal");
    const modalContent = document.getElementById("transcription-content");
    const closeButton = document.querySelector(".close-button");

    async function loadTranscriptions() {
        const response = await fetch("/transcriptions");
        const transcriptions = await response.json();

        tableBody.innerHTML = "";

        for (const transcription of transcriptions) {
            const row = document.createElement("tr");
            row.dataset.taskId = transcription.task_id;
            row.innerHTML = `
                <td>${transcription.task_id}</td>
                <td>${transcription.filename}</td>
                <td>${transcription.language}</td>
                <td class="status">pending</td>
                <td></td>
            `;
            tableBody.appendChild(row);
            pollStatus(transcription.task_id);
        }
    }

    async function pollStatus(taskId) {
        const response = await fetch(`/status/${taskId}`);
        const data = await response.json();

        const row = document.querySelector(`tr[data-task-id="${taskId}"]`);
        const statusCell = row.querySelector(".status");
        const actionsCell = row.querySelector("td:last-child");

        statusCell.textContent = data.status;

        if (data.status === "completed") {
            const resultPath = data.result.output_path || data.result.result;
            actionsCell.innerHTML = `<button class="view-button" data-path="${resultPath}" data-file-type="${data.file_type}">View</button>`;
        } else if (data.status === "failed") {
            actionsCell.innerHTML = `<button class="view-error-button" data-error="${data.error}">View Error</button>`;
        } else {
            setTimeout(() => pollStatus(taskId), 5000);
        }
    }

    tableBody.addEventListener("click", async (event) => {
        if (event.target.classList.contains("view-button")) {
            const button = event.target;
            const path = button.dataset.path;
            const fileType = button.dataset.fileType;

            modalContent.innerHTML = ""; // Clear previous content

            if (fileType === "video") {
                const video = document.createElement("video");
                video.src = `/${path}`;
                video.controls = true;
                video.style.maxWidth = "100%";
                modalContent.appendChild(video);
            } else if (fileType === "audio") {
                const audio = document.createElement("audio");
                audio.src = `/${path}`;
                audio.controls = true;
                modalContent.appendChild(audio);
            } else {
                const response = await fetch(`/${path}`);
                const content = await response.text();
                modalContent.textContent = content;
            }

            modal.style.display = "block";
        } else if (event.target.classList.contains("view-error-button")) {
            const error = event.target.dataset.error;
            modalContent.textContent = error;
            modal.style.display = "block";
        }
    });

    closeButton.addEventListener("click", () => {
        modal.style.display = "none";
    });

    window.addEventListener("click", (event) => {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    });

    loadTranscriptions();
});
