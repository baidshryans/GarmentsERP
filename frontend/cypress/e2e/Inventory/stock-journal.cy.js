describe(' Add Stock Journal Component', () => {
  it('should render the stock journal form', () => {
    cy.visit("/stockjournal/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });
  cy.wait(4000);
  cy.get('input[name="form.remarks"]').type('gg');
  
  cy.get('input[name="form.remarks"]').realPress('Tab');

  // issuse doctype to check
  cy.wait(3000);
  cy.get('input[name="table.packet"]').type('DR0004');
  cy.wait(4000);

  cy.get('[data-testid="select-purity"]').click();
  cy.get('[role="option"]').contains('18').click();
  cy.wait(2000);
  
  cy.get('[data-testid="doc-type"]').click();
  cy.get('[role="option"]').contains('Issue').click();

  cy.get('input[name="table.pcs"]').type('5');

  cy.get('input[name="table.ct"]').type('3');

  cy.get('input[name="table.gw"]').type('6');
  cy.get('input[name="table.gw"]').realPress('Tab');
  
  // receive doctype to check
  
  cy.get('input[name="table.packet"]').type('DR0008');
  cy.wait(4000);

  cy.get('[data-testid="select-purity"]').click();
  cy.get('[role="option"]').contains('24').click();
  cy.wait(2000);
  
  cy.get('[data-testid="doc-type"]').click();
  cy.get('[role="option"]').contains('Receive').click();

  cy.get('input[name="table.pcs"]').type('5');

  cy.get('input[name="table.ct"]').type('3');

  cy.get('input[name="table.gw"]').type('6');
  cy.get('input[name="table.gw"]').realPress('Tab');  
  cy.wait(2000);

  cy.get('button[type="submit"]').click();
  cy.wait(2000);

  cy.visit('/stockjournal/');
 });
});        