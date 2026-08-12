// Digital Signature Canvas Handler
document.addEventListener('DOMContentLoaded', function () {
    const canvas = document.getElementById('signature-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const clearBtn = document.getElementById('clear-signature');
    const signatureInput = document.getElementById('id_signature_data');

    let isDrawing = false;
    let hasSignature = false;

    // Set line properties
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0f172a';

    function getPos(e) {
        const rect = canvas.getBoundingClientRect();
        let clientX = e.clientX;
        let clientY = e.clientY;

        if (e.touches && e.touches.length > 0) {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        }

        return {
            x: clientX - rect.left,
            y: clientY - rect.top
        };
    }

    function startDrawing(e) {
        isDrawing = true;
        const pos = getPos(e);
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y);
        e.preventDefault();
    }

    function draw(e) {
        if (!isDrawing) return;
        const pos = getPos(e);
        ctx.lineTo(pos.x, pos.y);
        ctx.stroke();
        hasSignature = true;
        updateInput();
        e.preventDefault();
    }

    function stopDrawing() {
        if (isDrawing) {
            isDrawing = false;
            ctx.closePath();
            updateInput();
        }
    }

    function updateInput() {
        if (hasSignature && signatureInput) {
            signatureInput.value = canvas.toDataURL('image/png');
        }
    }

    // Mouse Events
    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseleave', stopDrawing);

    // Touch Events for Mobile / Tablets
    canvas.addEventListener('touchstart', startDrawing, { passive: false });
    canvas.addEventListener('touchmove', draw, { passive: false });
    canvas.addEventListener('touchend', stopDrawing);

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            hasSignature = false;
            if (signatureInput) signatureInput.value = '';
        });
    }

    // Ensure signature input is populated prior to form submit
    const form = canvas.closest('form');
    if (form) {
        form.addEventListener('submit', function () {
            if (hasSignature) {
                updateInput();
            }
        });
    }
});
