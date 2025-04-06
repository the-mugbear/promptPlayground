// communication_log.js
function appendChatMessage(data) {
    var chatHtml = "";
    chatHtml += '<div class="chat-row left"><div class="chat-bubble"><strong>Sent (Prompt):</strong><pre>' + data.prompt + '</pre></div></div>';
    chatHtml += '<div class="chat-row right"><div class="chat-bubble"><strong>Received (Response):</strong><pre>' + data.response + '</pre></div></div>';
    $("#chat_log").append(chatHtml);
  }
  
  function setupStream(url) {
    var source = new EventSource(url);
    source.onmessage = function(event) {
      var data = JSON.parse(event.data);
      appendChatMessage(data);
      if (data.final) {
        source.close();
      }
    };
    source.onerror = function() {
      $("#chat_log").append("<p>Error receiving stream.</p>");
      source.close();
    };
  }
  