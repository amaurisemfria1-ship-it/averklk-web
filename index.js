require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const session = require('express-session');
const MongoStore = require('connect-mongo');
const path = require('path');
const { checkCard } = require('./gates/mockGateway');

const app = express();
const PORT = process.env.PORT || 3000;

// Conexión a MongoDB
const mongoUri = process.env.MONGO_URI;
if (!mongoUri) {
  console.error('Error: La variable de entorno MONGO_URI no está definida.');
  process.exit(1);
}

mongoose.connect(mongoUri)
  .then(() => console.log('Conectado a MongoDB...'))
  .catch(err => console.error('No se pudo conectar a MongoDB...', err));

// Middlewares
app.use(express.urlencoded({ extended: true }));
app.use(express.static('public'));

// Configuración de la sesión
app.use(session({
  secret: process.env.SESSION_SECRET || 'un_secreto_por_defecto_muy_seguro',
  resave: false,
  saveUninitialized: true,
  store: MongoStore.create({
    mongoUrl: mongoUri,
    collectionName: 'sessions'
  }),
  cookie: { secure: process.env.NODE_ENV === 'production' }
}));

// Configurar EJS como motor de plantillas
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Middleware para proteger rutas
const requireLogin = (req, res, next) => {
  if (req.session && req.session.userId) {
    return next();
  } else {
    res.redirect('/login');
  }
};

// Rutas
app.get('/', (req, res) => {
  if (req.session && req.session.userId) {
    res.redirect('/dashboard');
  } else {
    res.redirect('/login');
  }
});

app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (username === process.env.ADMIN_USER && password === process.env.ADMIN_PASS) {
    req.session.userId = username;
    res.redirect('/dashboard');
  } else {
    res.render('login', { error: 'Usuario o contraseña incorrectos.' });
  }
});

app.get('/dashboard', requireLogin, (req, res) => {
  res.render('dashboard', { user: req.session.userId, results: [] });
});

app.post('/check', requireLogin, async (req, res) => {
  const { cards } = req.body;
  if (!cards) {
    return res.render('dashboard', { user: req.session.userId, results: [] });
  }

  const cardList = cards.split('\n').map(c => c.trim()).filter(c => c);
  const results = [];

  for (const card of cardList) {
    const ccNumber = card.split('|')[0];
    const result = await checkCard(ccNumber);
    results.push({ card, ...result });
  }

  res.render('dashboard', { user: req.session.userId, results });
});

app.post('/logout', (req, res) => {
  req.session.destroy(err => {
    if (err) {
      return res.redirect('/dashboard');
    }
    res.clearCookie('connect.sid');
    res.redirect('/login');
  });
});

// Iniciar el servidor
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Servidor corriendo en el puerto ${PORT}`);
});
