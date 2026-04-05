/// Working///

describe('Sales Return Component', () => {
  it('should render the sales return form', () => {
    cy.visit('sales/salesreturn/list/add/', {
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b');
        window.localStorage.setItem('retail_code', 'asfa');
      },
    });


  cy.wait(5000);
  cy.get('input[name="billno"]').type('SV/asfa/23232/00006')
  cy.get('input[name="billno"]').realPress('Tab');

  cy.wait(2000);

  cy.get('button[type="submit"]').click();
  cy.wait(3000);
  
  cy.visit('sales/salesreturn/list/')
  });
});    