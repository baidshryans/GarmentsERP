
describe(' Add Ledger Component', () => {
  it('should render the add ledger form', () => {
    cy.visit("/ledger/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

  // 1. Personal Information
  cy.wait(1000);

  cy.get('input[name="ac_name"]').type('KRS');

  cy.get('input[name="display_name"]').type('krs');

  cy.get('[data-testid="select-type"]').click();
  cy.get('[role="option"]').contains('KARIGAR').click();

  cy.get('[data-testid="account-group"]').click();
  cy.get('[role="option"]').contains('Assets').click();

  cy.get('input[name="dob"]').type('2000-02-02');

  cy.get('input[name="anniversary"]').type('2025-08-20');

  cy.wait(3000);

 //2. Contact Information

  cy.get('input[name="add1"]').type('WB');

  cy.get('input[name="pincode"]').type('786549');

  cy.get('[data-testid="state"]').click();
  cy.get('[role="option"]').contains('West Bengal').click();

  cy.get('input[name="phone1"]').type('9898988767');

  cy.get('input[name="mobile1"]').type('7865489737');

  cy.get('input[name="email"]').type('kr@gmail.com');

  //3. Financial Information

  // cy.get('input[name="pan"]').type('');

  // cy.get('input[name="gst"]').type('');

  // cy.get('input[name="aadhar"]').type('');

  // cy.get('input[name="passport"]').type('');

  // cy.get('input[name="dl_no"]').type('');

  // cy.get('input[name="remarks"]').type('');
  
  cy.wait(500);

  cy.get('button[type="submit"]').click();

  cy.wait(1500);

  cy.visit('/ledger');
  
 });
});      