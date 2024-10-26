const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const showSignup = document.getElementById("showSignup");
const showLogin = document.getElementById("showLogin");
const confirmPasswordInput = document.getElementById("confirmPassword");
const passwordInput = document.getElementById("password");

showSignup.addEventListener("click", (e) => {
    e.preventDefault();
    loginForm.style.display = "none";
    signupForm.style.display = "block";
});

showLogin.addEventListener("click", (e) => {
    e.preventDefault();
    signupForm.style.display = "none";
    loginForm.style.display = "block";
});

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = loginForm.querySelector('input[name="username"]').value;
    const password = loginForm.querySelector('input[name="password"]').value;

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('token', data.token);
            alert("Login successful!");
            window.location.href = "/home";
        } else {
            alert(data.error || "An error occurred during login.");
        }
    } catch (error) {
        console.error("An error occurred:", error);
        alert("An error occurred. Please try again.");
    }
});

signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const username = signupForm.querySelector('input[name="username"]').value;
    const email = signupForm.querySelector('input[name="email"]').value;
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (password !== confirmPassword) {
        alert("Passwords do not match. Please try again.");
        return;
    }

    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, email, password }),
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('token', data.token);
            alert("Signup successful!");
            window.location.href = "/home";
        } else {
            alert(data.error || "An error occurred during signup.");
        }
    } catch (error) {
        console.error("An error occurred:", error);
        alert("An error occurred. Please try again.");
    }
});