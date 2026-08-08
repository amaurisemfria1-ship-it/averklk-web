// index.js
require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const session = require('express-session');
const MongoStore = require('connect-mongo');
const path = require('path');
const { checkCard } = require('./gates/mockGateway');

const app = express();
const PORT = process.env.PORT || 3000;

// --- Conexión a MongoDB ---
// Railway inyectará la variable MONGO_URI automáticamente.
const mongoUri = process.env.MONGO_URI;
if (!mongoUri) {
  console.error('Error: La variable de entorno MONGO_URI no está definida.');
  process.exit(1); // Detiene la aplicación si la URI de la base de datos no está presente.
}
mongoose.connect(mongoUri)
  .then(() => console.log('Conectado a MongoDB...'))
  .catch(err => console.error('No se pudo conectar a MongoDB...', err));

// --- Middlewares ---
app.use(express.urlencoded({ extended: true })); // Para parsear datos de formularios.
app.use(express.static('public')); // Para servir archivos estáticos (CSS, JS, imágenes).

// Confiar en el proxy de Railway para la configuración de cookies seguras.
app.set('trust proxy', 1);

// Configuración de la sesión
app.use(session({
  secret: process.env.SESSION_SECRET || 'un_secreto_por_defecto_muy_seguro',
  resave: false,
  saveUninitialized: true,
  store: MongoStore.create({ 
    mongoUrl: mongoUri,
    collectionName: 'sessions' // Nombre de la colección donde se guardarán las sesiones
  }),
  // En producción (como en Railway), la cookie debe ser segura (HTTPS).
  cookie: { secure: process.env.NODE_ENV === 'production' } 
}));

// Configurar EJS como motor de plantillas y la carpeta de vistas.
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// --- Middleware para proteger rutas ---
const requireLogin = (req, res, next) => {
  if (req.session && req.session.userId) {
    return next(); // El usuario está logueado, puede continuar.
  } else {
    return res.redirect('/login'); // No está logueado, se redirige al login.
  }
};

// --- Rutas de la aplicación ---

// Ruta principal: redirige al dashboard si está logueado, si no, al login.
app.get('/', (req, res) => {
  if (req.session.userId) {
    res.redirect('/dashboard');
  } else {
    res.redirect('/login');
  }
});

// Ruta para mostrar el formulario de login.
app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

// Ruta para procesar los datos del formulario de login.
app.post('/login', (req, res, next) => { // 1. Añadir 'next' a los parámetros.
  const { username, password } = req.body;

  // Comparamos con las credenciales de las variables de entorno.
  if (username === process.env.ADMIN_USER && password === process.env.ADMIN_PASS) {
    // Guardamos el usuario en la sesión.
    req.session.userId = username; 
    // Nos aseguramos de que la sesión se guarde antes de redirigir.
    req.session.save(err => {
      if (err) {
        console.error("Error al guardar la sesión:", err);
        return next(err);
      }
      res.redirect('/dashboard'); // Redirigimos solo después de guardar.
    });
  } else {
    res.render('login', { error: 'Usuario o contraseña incorrectos.' });
  }
});

// Ruta del panel de control (protegida por el middleware requireLogin).
app.get('/dashboard', requireLogin, (req, res) => {
  // Renderiza el dashboard sin resultados la primera vez.
  res.render('dashboard', { user: req.session.userId, results: [] });
});

// Ruta para procesar la verificación de tarjetas.
app.post('/check', requireLogin, async (req, res) => {
  const { cards } = req.body;
  if (!cards) {
    return res.render('dashboard', { user: req.session.userId, results: [] });
  }

  // Separa cada línea en un array y elimina las vacías.
  const cardList = cards.split('\n').map(c => c.trim()).filter(c => c);

  const results = [];
  for (const card of cardList) {
    const ccNumber = card.split('|')[0]; // Extrae solo el número de la tarjeta.
    const result = await checkCard(ccNumber);
    results.push({ card: card, ...result });
  }

  res.render('dashboard', { user: req.session.userId, results: results });
});

// Ruta para cerrar sesión.
app.post('/logout', (req, res) => {
  req.session.destroy(err => {
    if (err) {
      return res.redirect('/dashboard');
    }
    res.clearCookie('connect.sid'); // Limpia la cookie de sesión del navegador.
    res.redirect('/login');
  });
});

// Iniciar el servidor.
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Servidor corriendo en el puerto ${PORT}`);
});
