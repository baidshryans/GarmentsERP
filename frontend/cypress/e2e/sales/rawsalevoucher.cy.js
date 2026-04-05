
describe('RawSale Voucher Component', () => {
  it('should render the rawsale Voucher form', () => {
    cy.visit("/sales/rawsalesvoucher/list/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });
 



 cy.wait(2000);
 cy.get('input[name="form.gst_billno"]').type('0004');
 cy.wait(1500);

 cy.get('input[name="form.ldgr_name"]').type('A.Chhajer');
 
 cy.get('[data-testid="sales-person1"]').click();
 cy.wait(1000);
 cy.get('[role="option"]').contains('Jane Smith').click();

cy.get('[data-testid="sales-person2"]').click();
cy.get('[role="option"]').contains('Emily Davis').click();

// cy.get('[data-testid="place-of-supply"]').click(); 
// cy.get('[role="option"]').contains('Rajasthan').click();

cy.get('input[name="form.remarks"]').type('ok');

cy.get('input[name="form.mode_of_transport"]').type('ffd');


// item details //

  
    cy.get('input[name="details.packet"]').type('DR0007');

    // cy.get('input[name="details.sub_item"]').type('GNS');

    cy.get('input[name="details.sub_pcs"]').type('2');

    cy.get('input[name="details.sub_ct"]').type('0.02');

    cy.get('input[name="details.sub_gw"]').type('0.01');

    cy.get('[data-testid="select-purity"]').click();
    cy.get('[role="option"]').contains('24').click();

    cy.get('input[name="details.loss"]').type('0.1');

    cy.get('input[name="details.tunch"]').type('0.02');

    cy.get('input[name="details.fine_wt"]').type('0.01');

    cy.get('input[name="details.rate"]').type('0.06');

    cy.get('input[name="details.value"]').type('0.00');
    cy.wait(500);
    cy.get('input[name="details.value"]').realPress('Tab');
    cy.wait(1000);

    cy.get('input[name="form.cash"]').type('200');


/// payments details ////


cy.get('input[name="bank.amount"]').type('10');

cy.get('input[name="bank.chq_no"]').type('12345');

cy.get('input[name="bank.bank_name"]').type('CASH');

cy.get('input[name="bank.jij_bank"]').type('adq');

cy.get('input[name="bank.chq_date"]').type('2025-07-30');

// cy.get('[data-testid="btn"]').click();

/// Bill summary///


cy.get('input[name="form.freight_charge"]').type('1');

// cy.get('input[name="form.mrp"]').type('1');

 cy.get('input[name="form.other_charge"]').type('1');

 cy.get('input[name="form.discount"]').type('0.01');

 cy.get('input[name="form.round_off"]').type('0.01');

 cy.get('button[type="submit"]').click();

 
  });
});