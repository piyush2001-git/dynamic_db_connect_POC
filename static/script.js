// script.js

document.addEventListener("DOMContentLoaded", function () {
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatContainer = document.getElementById("chat-container");
    const urlForm = document.getElementById("url-form");
    const authCheckbox = document.getElementById("authCheckbox");
    const tokenInput = document.getElementById("tokenInput");
  
    // Append a message to the chat container
    function appendMessage(text, sender) {
      const messageElem = document.createElement("div");
      messageElem.classList.add("message", sender);
      messageElem.textContent = text;
      chatContainer.appendChild(messageElem);
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  
    // Toggle token input visibility based on checkbox
    authCheckbox.addEventListener("change", function () {
      tokenInput.style.display = this.checked ? "block" : "none";
    });
  
    // Handle chat form submission
    chatForm.addEventListener("submit", function (e) {
      e.preventDefault();
      const message = chatInput.value.trim();
      if (!message) return;
      appendMessage(message, "user");
      chatInput.value = "";
      const formData = new URLSearchParams();
      formData.append("query", message);
  
      fetch("/", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: formData
      })
      .then(response => {
        if (!response.ok) throw new Error("Network response was not ok");
        return response.json();
      })
      .then(data => {
        appendMessage(data.result, "agent");
      })
      .catch(error => {
        console.error("Error:", error);
        appendMessage("Error retrieving agent response.", "agent");
      });
    });
  
    // Handle URL form submission via AJAX
    urlForm.addEventListener("submit", function (e) {
      e.preventDefault();
      const urlInput = document.getElementById("documentUrl");
      const urlValue = urlInput.value.trim();
      if (!urlValue) return;
      appendMessage("Uploading document...", "user");
      const formData = new URLSearchParams();
      formData.append("documentUrl", urlValue);
      if (authCheckbox.checked) {
        const tokenValue = document.getElementById("oauthToken").value.trim();
        if (tokenValue) {
          formData.append("oauthToken", tokenValue);
        } else {
          appendMessage("Please enter an OAuth token.", "agent");
          return;
        }
      }
  
      fetch("/", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: formData
      })
      .then(response => {
        if (!response.ok) throw new Error("Network response was not ok");
        return response.json();
      })
      .then(data => {
        appendMessage(data.result, "agent");
        urlInput.value = "";
        if (authCheckbox.checked) {
          document.getElementById("oauthToken").value = ""; // Clear token
        }
        const urlModalElem = document.getElementById("urlModal");
        const urlModal = bootstrap.Modal.getInstance(urlModalElem);
        if (urlModal) urlModal.hide();
      })
      .catch(error => {
        console.error("Error:", error);
        appendMessage("Error uploading document URL.", "agent");
      });
    });
  });