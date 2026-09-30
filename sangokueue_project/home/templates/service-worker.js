self.addEventListener("push", function(event) {
    const data = event.data ? event.data.json() : {};

    event.waitUntil(
        self.registration.showNotification(
            data.title || "SanGoKueue",
            {
                body: data.message || "Nouvelle notification",
                icon: "/static/home/images/logo.png"
            }
        )
    );
});