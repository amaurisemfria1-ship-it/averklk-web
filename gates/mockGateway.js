// gates/mockGateway.js

/**
 * Simula la verificación de una tarjeta de crédito.
 * En una aplicación real, aquí iría la lógica para comunicarse
 * con una API de pago como Stripe.
 * 
 * @param {string} ccNumber El número de la tarjeta de crédito.
 * @returns {Promise<{success: boolean, message: string}>}
 */
function checkCard(ccNumber) {
  return new Promise(resolve => {
    // Simulación: Las tarjetas que terminan en '4242' son aprobadas.
    // Todas las demás son rechazadas. Esta es una lógica de prueba común.
    if (ccNumber && ccNumber.endsWith('4242')) {
      setTimeout(() => resolve({ success: true, message: 'APROBADA ✅ - Tarjeta de prueba válida.' }), 500);
    } else {
      setTimeout(() => resolve({ success: false, message: 'RECHAZADA ❌ - La tarjeta no es válida.' }), 500);
    }
  });
}

module.exports = { checkCard };
