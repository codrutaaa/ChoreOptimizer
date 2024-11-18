function markComplete(taskId) {
    axios.post(`/update/${taskId}`)
        .then(response => {
            if (response.data.success) {
                location.reload();
            }
        })
        .catch(error => console.error("Error updating task:", error));
}

function deleteTask(taskId) {
    axios.post(`/delete/${taskId}`)
        .then(response => {
            if (response.data.success) {
                location.reload();
            }
        })
        .catch(error => console.error("Error deleting task:", error));
}
