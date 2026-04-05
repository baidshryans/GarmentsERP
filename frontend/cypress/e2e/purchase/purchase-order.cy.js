/// working///

describe('Purchase Order Component', () => {
  it('should render the purchase order form', () => {
    cy.visit('purchase/purchaseorder/list/add/',{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });
    
    cy.get('input[name="form.po_no"]').type('PO/asfa/23232/00010');

    cy.get('[data-testid="slip"]').click(); 
    cy.get('[role="option"]').contains('Customer Order').click();
    
    cy.get('[data-testid="state"]').click();
    cy.wait(1500);
    cy.get('[role="option"]').contains('Assam').click();


    cy.get('input[name="form.ldgr_name"]').type('A. Maity');

    


    cy.get('input[name="table.ref_job_object_id"]').type('C2324/00010',{force:true});

    cy.get('input[name="table.job_sl_object_id"]').type('2',{force:true});



    /// Item Details///

    cy.get('input[name="table.po_sl_no"]').type('1');

    cy.get('input[name="table.design_code"]').type('2');

    cy.get('input[name="table.item"]').type('GNS');

    cy.get('[data-testid="purity"]').click()
    cy.get('[role="option"]').contains('24').click();

    cy.get('input[name="table.pcs"]').type('5');

    cy.get('input[name="table.approx_wt"]').type('10');

    cy.get('input[name="table.size"]').type('2');

    cy.get('input[name="table.due_date"]').type('2025-06-26');

    cy.get('input[name="table.remarks"]').type('gg');

    cy.get('input[name="table.remarks"]').type('gg');
    cy.get('input[name="table.remarks"]').realPress('Tab');

    cy.get('button[type="submit"]').click();

     cy.visit('purchase/purchaseorder/list/');

  });
});
  



