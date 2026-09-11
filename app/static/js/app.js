document.addEventListener("DOMContentLoaded", () => {
    const actualizarMenuPorHash = () => {
        const enlaces = document.querySelectorAll(".enlace-menu");
        if (!enlaces.length || window.location.pathname !== "/") return;
        const seccion = window.location.hash === "#modulos" ? "modulos" : "inicio";
        enlaces.forEach((enlace) => {
            const activo = enlace.dataset.seccion === seccion;
            enlace.classList.toggle("activo", activo);
            if (activo) enlace.setAttribute("aria-current", "page");
            else enlace.removeAttribute("aria-current");
        });
    };
    actualizarMenuPorHash();
    window.addEventListener("hashchange", actualizarMenuPorHash);

    const botonEstado = document.querySelector("#boton-estado");
    const botonDemo = document.querySelector("#boton-demo");
    const textoEstado = document.querySelector("#texto-estado");
    const notificacion = document.querySelector("#notificacion");

    const colocarTexto = (selector, valor) => {
        const elemento = document.querySelector(selector);
        if (elemento) elemento.textContent = valor;
    };

    const avisar = (mensaje) => {
        notificacion.textContent = mensaje;
        notificacion.classList.add("visible");
        window.setTimeout(() => notificacion.classList.remove("visible"), 3200);
    };

    const cargarSalud = async (mostrarAviso = false) => {
        try {
            const respuesta = await fetch("/salud");
            if (!respuesta.ok) throw new Error("Sin conexión");
            const datos = await respuesta.json();
            colocarTexto("#dato-base", datos.base_datos);
            colocarTexto("#dato-tablas", datos.tablas);
            if (botonEstado) botonEstado.classList.add("conectado");
            if (textoEstado) textoEstado.textContent = "Sistema conectado";
            if (mostrarAviso) avisar(`Impulsa está conectada a ${datos.base_datos} con ${datos.tablas} tablas.`);
        } catch (error) {
            colocarTexto("#dato-base", "Sin conexión");
            if (textoEstado) textoEstado.textContent = "Revisar conexión";
            if (mostrarAviso) avisar("No fue posible comprobar la base de datos.");
        }
    };

    const cargarResumen = async () => {
        try {
            const respuesta = await fetch("/api/resumen");
            if (!respuesta.ok) return;
            const datos = await respuesta.json();
            colocarTexto("#total-roles", datos.roles);
            colocarTexto("#total-usuarios", datos.usuarios);
            colocarTexto("#total-cursos", datos.cursos);
            colocarTexto("#total-sesiones", datos.sesiones);
        } catch (error) {
            console.info("El resumen estará disponible cuando la base esté conectada.");
        }
    };

    document.querySelectorAll("button.modulo").forEach((modulo) => {
        modulo.addEventListener("click", () => {
            const activo = modulo.classList.toggle("is-active");
            modulo.setAttribute("aria-expanded", String(activo));
        });
    });

    if (botonEstado) botonEstado.addEventListener("click", () => cargarSalud(true));
    if (botonDemo) botonDemo.addEventListener("click", () => cargarSalud(true));
    if (document.querySelector("#dato-base")) cargarSalud();
    cargarResumen();

    const mostrarPassword = document.querySelector("#mostrar-password");
    if (mostrarPassword) {
        mostrarPassword.addEventListener("click", () => {
            const campo = document.querySelector("#password");
            const visible = campo.type === "text";
            campo.type = visible ? "password" : "text";
            mostrarPassword.textContent = visible ? "Ver" : "Ocultar";
        });
    }

    const cronometro = document.querySelector("#cronometro");
    if (cronometro) {
        const inicio = new Date(cronometro.dataset.inicio).getTime();
        const pausasPrevias = Number(cronometro.dataset.pausas || 0) * 1000;
        const pausaInicio = cronometro.dataset.pausaInicio
            ? new Date(cronometro.dataset.pausaInicio).getTime()
            : null;
        const actualizarCronometro = () => {
            const momento = pausaInicio || Date.now();
            const segundos = Math.max(0, Math.floor((momento - inicio - pausasPrevias) / 1000));
            const horas = String(Math.floor(segundos / 3600)).padStart(2, "0");
            const minutos = String(Math.floor((segundos % 3600) / 60)).padStart(2, "0");
            const resto = String(segundos % 60).padStart(2, "0");
            cronometro.textContent = `${horas}:${minutos}:${resto}`;
        };
        actualizarCronometro();
        if (!pausaInicio) window.setInterval(actualizarCronometro, 1000);
    }

    const archivoEvidencia = document.querySelector("#archivo-evidencia");
    if (archivoEvidencia) {
        archivoEvidencia.addEventListener("change", () => {
            const nombre = document.querySelector("#nombre-archivo");
            nombre.textContent = archivoEvidencia.files.length
                ? `Seleccionado: ${archivoEvidencia.files[0].name}`
                : "Ningún archivo seleccionado";
        });
    }
});
